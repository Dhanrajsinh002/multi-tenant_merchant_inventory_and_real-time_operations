import re
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis
from app.core.errors import CleanDeskException, ErrorCode
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.merchant import Merchant
from app.models.user import User, UserRole
from app.schemas.auth import (
    LoginRequest,
    MerchantRegisterRequest,
    MerchantResponse,
    Token,
    UserResponse,
)
from app.services.rate_limiter import SlidingWindowRateLimiter

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register_merchant(
    payload: MerchantRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Registers a new Merchant workspace + OWNER user in a single atomic transaction.
    Issues JWT token containing user_id, merchant_id, and role.
    """
    # Check if merchant slug already exists
    existing_slug = await db.execute(select(Merchant).where(Merchant.slug == payload.merchant_slug))
    if existing_slug.scalar_one_or_none():
        raise CleanDeskException(
            status_code=status.HTTP_409_CONFLICT,
            error_code=ErrorCode.INVALID_BULK_PAYLOAD,
            message=f"Merchant with slug '{payload.merchant_slug}' already exists."
        )

    # Check if user email already exists
    existing_email = await db.execute(select(User).where(User.email == payload.email))
    if existing_email.scalar_one_or_none():
        raise CleanDeskException(
            status_code=status.HTTP_409_CONFLICT,
            error_code=ErrorCode.INVALID_BULK_PAYLOAD,
            message=f"User with email '{payload.email}' already exists."
        )

    try:
        # Create Merchant workspace
        merchant = Merchant(
            name=payload.merchant_name,
            slug=payload.merchant_slug,
            status="ACTIVE"
        )
        db.add(merchant)
        await db.flush()  # Populates merchant.id

        # Create initial OWNER user
        owner_user = User(
            merchant_id=merchant.id,
            name=payload.owner_name,
            email=payload.email,
            password_hash=get_password_hash(payload.password),
            role=UserRole.OWNER.value
        )
        db.add(owner_user)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # Generate JWT with user_id, merchant_id, and role
    access_token = create_access_token(
        user_id=owner_user.id,
        merchant_id=merchant.id,
        role=owner_user.role
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(owner_user),
        merchant=MerchantResponse.model_validate(merchant)
    )


@router.post("/login", response_model=Token)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Authenticates user and returns JWT.
    Protected by Redis-backed sliding-window rate limiter (max 5 failed attempts per minute).
    """
    client_ip = request.client.host if request.client else "unknown"
    rate_limiter = SlidingWindowRateLimiter(redis_client)
    rate_limit_identifier = f"{client_ip}:{payload.email}"

    # 1. Enforce Sliding Window Rate Limit (Raises 429 if exceeded)
    await rate_limiter.check_rate_limit(rate_limit_identifier)

    # 2. Look up user by email
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # 3. Check credentials
    if not user or not verify_password(payload.password, user.password_hash):
        # Record failed attempt atomically in Redis
        await rate_limiter.record_failed_attempt(rate_limit_identifier)
        raise CleanDeskException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=ErrorCode.CROSS_TENANT_ACCESS_DENIED,
            message="Invalid email or password."
        )

    # 4. Fetch associated merchant
    merchant_res = await db.execute(select(Merchant).where(Merchant.id == user.merchant_id))
    merchant = merchant_res.scalar_one_or_none()

    if not merchant or merchant.status != "ACTIVE":
        raise CleanDeskException(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=ErrorCode.CROSS_TENANT_ACCESS_DENIED,
            message="Merchant workspace is inactive or suspended."
        )

    # 5. Clear rate limit counter on successful login
    await rate_limiter.reset_attempts(rate_limit_identifier)

    # 6. Issue JWT with user_id, merchant_id, and role
    access_token = create_access_token(
        user_id=user.id,
        merchant_id=user.merchant_id,
        role=user.role
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
        merchant=MerchantResponse.model_validate(merchant)
    )