from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.models.approval import ApprovalStatus, StockApprovalRequest
from app.models.product import Product
from app.models.user import User
from app.schemas.dashboard import DashboardMetrics
from app.services.cache import CacheService

router = APIRouter()


@router.get("/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Returns tenant operational KPIs:
    - Total SKUs
    - Total Inventory Valuation
    - Low Stock Count
    - Pending Approvals

    Implements Redis Cache-Aside with graceful degradation to PostgreSQL.
    """
    cache_service = CacheService(redis_client)
    cache_key = cache_service.dashboard_key(current_user.merchant_id)

    # 1. Cache-Aside: Try fetching from Redis first
    cached_data = await cache_service.get_json(cache_key)
    if cached_data:
        cached_data["from_cache"] = True
        return DashboardMetrics(**cached_data)

    # 2. Fallback to PostgreSQL queries (strictly scoped by current_user.merchant_id)
    # Total SKUs
    sku_query = select(func.count(Product.id)).where(Product.merchant_id == current_user.merchant_id)
    sku_res = await db.execute(sku_query)
    total_skus = sku_res.scalar() or 0

    # Total Inventory Value (SUM(stock_quantity * unit_price))
    value_query = select(
        func.coalesce(func.sum(Product.stock_quantity * Product.unit_price), 0.0)
    ).where(Product.merchant_id == current_user.merchant_id)
    val_res = await db.execute(value_query)
    total_inventory_value = float(val_res.scalar() or 0.0)

    # Low Stock Count (WHERE stock_quantity <= low_stock_threshold)
    # Uses composite index: ix_products_merchant_low_stock
    low_stock_query = select(func.count(Product.id)).where(
        Product.merchant_id == current_user.merchant_id,
        Product.stock_quantity <= Product.low_stock_threshold
    )
    low_res = await db.execute(low_stock_query)
    low_stock_count = low_res.scalar() or 0

    # Pending Approvals (WHERE status = 'PENDING')
    # Uses composite index: ix_approvals_merchant_status
    pending_query = select(func.count(StockApprovalRequest.id)).where(
        StockApprovalRequest.merchant_id == current_user.merchant_id,
        StockApprovalRequest.status == ApprovalStatus.PENDING.value
    )
    pending_res = await db.execute(pending_query)
    pending_approvals = pending_res.scalar() or 0

    metrics_data = {
        "total_skus": total_skus,
        "total_inventory_value": round(total_inventory_value, 2),
        "low_stock_count": low_stock_count,
        "pending_approvals": pending_approvals,
    }

    # 3. Store in Redis with TTL (e.g., 300 seconds)
    await cache_service.set_json(cache_key, metrics_data, ttl_seconds=300)

    metrics_data["from_cache"] = False
    return DashboardMetrics(**metrics_data)