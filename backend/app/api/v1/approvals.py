from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db, get_redis, require_owner
from app.core.errors import CleanDeskException, ErrorCode
from app.models.approval import ApprovalStatus, StockApprovalRequest
from app.models.product import Product
from app.models.user import User
from app.schemas.approval import ApprovalCreate, ApprovalDecision, ApprovalResponse
from app.services.cache import CacheService
from app.services.websocket_manager import WebSocketEventType, ws_manager

router = APIRouter()


def _to_approval_response(req: StockApprovalRequest) -> ApprovalResponse:
    return ApprovalResponse(
        id=req.id,
        merchant_id=req.merchant_id,
        product_id=req.product_id,
        product_sku=req.product.sku if req.product else None,
        product_name=req.product.name if req.product else None,
        requested_by=req.requested_by,
        requester_name=req.requester.name if req.requester else None,
        approved_by=req.approved_by,
        approver_name=req.approver.name if req.approver else None,
        quantity_delta=req.quantity_delta,
        reason=req.reason,
        status=req.status,
        created_at=req.created_at,
        resolved_at=req.resolved_at,
    )


@router.post("", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
async def create_stock_approval_request(
    payload: ApprovalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    STAFF or OWNER submits a stock adjustment request.
    Enforces tenant isolation on product_id.
    """
    # Verify product exists in the current tenant workspace
    prod_res = await db.execute(
        select(Product).where(
            Product.id == payload.product_id,
            Product.merchant_id == current_user.merchant_id
        )
    )
    product = prod_res.scalar_one_or_none()

    if not product:
        # Check foreign tenant to return 403 CROSS_TENANT_ACCESS_DENIED
        foreign_prod = await db.execute(select(Product).where(Product.id == payload.product_id))
        if foreign_prod.scalar_one_or_none():
            raise CleanDeskException(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code=ErrorCode.CROSS_TENANT_ACCESS_DENIED,
                message="Cannot request stock adjustment for product belonging to another merchant."
            )
        raise CleanDeskException(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=ErrorCode.NOT_FOUND,
            message=f"Product {payload.product_id} not found."
        )

    request_item = StockApprovalRequest(
        merchant_id=current_user.merchant_id,
        product_id=product.id,
        requested_by=current_user.id,
        quantity_delta=payload.quantity_delta,
        reason=payload.reason,
        status=ApprovalStatus.PENDING.value
    )
    db.add(request_item)
    await db.commit()
    await db.refresh(request_item)

    # Eager load relationships for clean response
    loaded = await db.execute(
        select(StockApprovalRequest)
        .options(
            selectinload(StockApprovalRequest.product),
            selectinload(StockApprovalRequest.requester),
            selectinload(StockApprovalRequest.approver)
        )
        .where(StockApprovalRequest.id == request_item.id)
    )
    full_request = loaded.scalar_one()
    resp = _to_approval_response(full_request)

    # Broadcast APPROVAL_CREATED event
    await ws_manager.broadcast_to_merchant(
        merchant_id=current_user.merchant_id,
        event_type=WebSocketEventType.APPROVAL_CREATED,
        data=resp.model_dump(mode="json")
    )

    return resp


@router.get("", response_model=List[ApprovalResponse])
async def get_approvals(
    status_filter: Optional[ApprovalStatus] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists pending or resolved requests strictly for the authenticated merchant.
    Uses composite index: ix_approvals_merchant_status.
    """
    query = select(StockApprovalRequest).options(
        selectinload(StockApprovalRequest.product),
        selectinload(StockApprovalRequest.requester),
        selectinload(StockApprovalRequest.approver)
    ).where(StockApprovalRequest.merchant_id == current_user.merchant_id)

    if status_filter:
        query = query.where(StockApprovalRequest.status == status_filter.value)

    query = query.order_by(StockApprovalRequest.created_at.desc())
    result = await db.execute(query)
    requests = result.scalars().all()
    return [_to_approval_response(r) for r in requests]


@router.post("/{approval_id}/decision", response_model=ApprovalResponse)
async def decide_stock_approval(
    approval_id: int,
    decision: ApprovalDecision,
    current_user: User = Depends(require_owner),  # OWNER only RBAC!
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    OWNER-only endpoint to approve or reject a stock adjustment.
    Upon approval:
    - Atomically updates Product.stock_quantity
    - Prevents negative stock (fails with INSUFFICIENT_STOCK)
    - Invalidates cache
    - Broadcasts APPROVAL_RESOLVED and STOCK_UPDATED
    """
    # 1. Fetch approval request
    res = await db.execute(
        select(StockApprovalRequest)
        .options(selectinload(StockApprovalRequest.product), selectinload(StockApprovalRequest.requester))
        .where(StockApprovalRequest.id == approval_id)
    )
    req = res.scalar_one_or_none()

    if not req:
        raise CleanDeskException(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=ErrorCode.NOT_FOUND,
            message=f"Approval request {approval_id} not found."
        )

    # Enforce cross-tenant isolation
    if req.merchant_id != current_user.merchant_id:
        raise CleanDeskException(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=ErrorCode.CROSS_TENANT_ACCESS_DENIED,
            message="Access denied: request belongs to another merchant workspace."
        )

    if req.status != ApprovalStatus.PENDING.value:
        raise CleanDeskException(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=ErrorCode.INVALID_BULK_PAYLOAD,
            message=f"Request is already resolved with status '{req.status}'."
        )

    # 2. Process Decision in an Atomic Transaction
    try:
        if decision.status == ApprovalStatus.APPROVED:
            # Lock product row
            prod_res = await db.execute(
                select(Product).where(Product.id == req.product_id).with_for_update()
            )
            product = prod_res.scalar_one()

            # Safeguard against negative stock
            new_stock = product.stock_quantity + req.quantity_delta
            if new_stock < 0:
                raise CleanDeskException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_code=ErrorCode.INSUFFICIENT_STOCK,
                    message=f"Cannot approve: stock cannot be negative (current: {product.stock_quantity}, delta: {req.quantity_delta})."
                )

            # Update stock
            product.stock_quantity = new_stock

        # Update request status
        req.status = decision.status.value
        req.approved_by = current_user.id
        req.resolved_at = datetime.utcnow()
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # Refresh for response
    await db.refresh(req)
    loaded = await db.execute(
        select(StockApprovalRequest)
        .options(
            selectinload(StockApprovalRequest.product),
            selectinload(StockApprovalRequest.requester),
            selectinload(StockApprovalRequest.approver)
        )
        .where(StockApprovalRequest.id == req.id)
    )
    updated_req = loaded.scalar_one()
    resp = _to_approval_response(updated_req)

    # 3. Explicit Invalidation: Clear Redis cache
    cache_service = CacheService(redis_client)
    await cache_service.invalidate_merchant_cache(current_user.merchant_id)

    # 4. Broadcast Real-Time Events
    await ws_manager.broadcast_to_merchant(
        merchant_id=current_user.merchant_id,
        event_type=WebSocketEventType.APPROVAL_RESOLVED,
        data=resp.model_dump(mode="json")
    )

    if decision.status == ApprovalStatus.APPROVED and updated_req.product:
        await ws_manager.broadcast_to_merchant(
            merchant_id=current_user.merchant_id,
            event_type=WebSocketEventType.STOCK_UPDATED,
            data={
                "product_id": updated_req.product.id,
                "sku": updated_req.product.sku,
                "stock_quantity": updated_req.product.stock_quantity
            }
        )

    return resp