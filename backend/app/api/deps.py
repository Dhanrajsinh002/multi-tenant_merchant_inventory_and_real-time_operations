from typing import AsyncGenerator, Optional
import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import CleanDeskException, ErrorCode
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import TokenPayload

# Bearer token security scheme
security = HTTPBearer(auto_error=False)

# Reusable async Redis client with graceful error handling
redis_client = aioredis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=2.0
)


async def get_redis() -> aioredis.Redis:
    """Provide async Redis client."""
    return redis_client


async def get_current_token_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> TokenPayload:
    """Extract and validate the JWT token from the Authorization header."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return TokenPayload(
            user_id=int(payload["user_id"]),
            merchant_id=int(payload["merchant_id"]),
            role=str(payload["role"]),
            exp=payload.get("exp")
        )
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    payload: TokenPayload = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Verify that the authenticated user exists in the database
    and belongs to the merchant_id claimed in the JWT.
    """
    query = select(User).where(
        User.id == payload.user_id,
        User.merchant_id == payload.merchant_id
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise CleanDeskException(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=ErrorCode.CROSS_TENANT_ACCESS_DENIED,
            message="User does not exist or does not belong to this merchant workspace."
        )
    return user


def require_role(required_role: UserRole):
    """
    Role-Based Access Control (RBAC) dependency factory.
    Blocks unauthorized roles with CleanDesk's UNAUTHORIZED_ROLE error code.
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != required_role.value:
            raise CleanDeskException(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code=ErrorCode.UNAUTHORIZED_ROLE,
                message=f"Action requires '{required_role.value}' role. Your role is '{current_user.role}'."
            )
        return current_user
    return role_checker


# Convenience dependency for OWNER-only routes
require_owner = require_role(UserRole.OWNER)