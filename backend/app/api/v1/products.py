import csv
import io
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.core.errors import CleanDeskException, ErrorCode
from app.models.product import Product
from app.models.user import User
from app.schemas.product import (
    PaginatedProductsResponse,
    ProductBulkItem,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.services.cache import CacheService
from app.services.websocket_manager import WebSocketEventType, ws_manager

router = APIRouter()


def _to_product_response(product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        merchant_id=product.merchant_id,
        sku=product.sku,
        name=product.name,
        category=product.category,
        unit_price=product.unit_price,
        stock_quantity=product.stock_quantity,
        low_stock_threshold=product.low_stock_threshold,
        is_low_stock=(product.stock_quantity <= product.low_stock_threshold),
        updated_at=product.updated_at,
    )


@router.get("", response_model=PaginatedProductsResponse)
async def get_products(
    category: Optional[str] = Query(None),
    low_stock: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Paginated catalog query filterable by category and low_stock=true.
    Implements Redis cache-aside for default catalog view (page 1, unfiltered).
    Strictly scoped to current_user.merchant_id.
    """
    cache_service = CacheService(redis_client)
    is_default_query = (category is None and low_stock is None and page == 1 and size == 20)
    cache_key = cache_service.products_key(current_user.merchant_id)

    if is_default_query:
        cached = await cache_service.get_json(cache_key)
        if cached:
            return PaginatedProductsResponse(**cached)

    # Build tenant-scoped query
    query = select(Product).where(Product.merchant_id == current_user.merchant_id)
    count_query = select(func.count(Product.id)).where(Product.merchant_id == current_user.merchant_id)

    if category:
        query = query.where(Product.category == category)
        count_query = count_query.where(Product.category == category)

    if low_stock is True:
        query = query.where(Product.stock_quantity <= Product.low_stock_threshold)
        count_query = count_query.where(Product.stock_quantity <= Product.low_stock_threshold)

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    # Pagination offset & limit
    query = query.order_by(Product.id.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    products = result.scalars().all()

    items = [_to_product_response(p) for p in products]
    pages = (total + size - 1) // size if total > 0 else 1
    response_data = {
        "items": [item.model_dump() for item in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }

    # Cache default list
    if is_default_query:
        await cache_service.set_json(cache_key, response_data, ttl_seconds=300)

    return PaginatedProductsResponse(**response_data)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Creates a new product in the merchant's catalog.
    Enforces tenant uniqueness on SKU, invalidates cache, and broadcasts WebSocket event.
    """
    # Check if SKU exists within this merchant
    existing = await db.execute(
        select(Product).where(
            Product.merchant_id == current_user.merchant_id,
            Product.sku == payload.sku
        )
    )
    if existing.scalar_one_or_none():
        raise CleanDeskException(
            status_code=status.HTTP_409_CONFLICT,
            error_code=ErrorCode.DUPLICATE_SKU,
            message=f"Product with SKU '{payload.sku}' already exists in your workspace."
        )

    product = Product(
        merchant_id=current_user.merchant_id,
        sku=payload.sku,
        name=payload.name,
        category=payload.category,
        unit_price=payload.unit_price,
        stock_quantity=payload.stock_quantity,
        low_stock_threshold=payload.low_stock_threshold
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)

    # Invalidate cache
    cache_service = CacheService(redis_client)
    await cache_service.invalidate_merchant_cache(current_user.merchant_id)

    resp = _to_product_response(product)

    # Broadcast real-time WebSocket event
    await ws_manager.broadcast_to_merchant(
        merchant_id=current_user.merchant_id,
        event_type=WebSocketEventType.STOCK_UPDATED,
        data=resp.model_dump(mode="json")
    )

    if resp.is_low_stock:
        await ws_manager.broadcast_to_merchant(
            merchant_id=current_user.merchant_id,
            event_type=WebSocketEventType.LOW_STOCK_ALERT,
            data={"product_id": product.id, "sku": product.sku, "stock_quantity": product.stock_quantity}
        )

    return resp


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Updates an existing product.
    Strictly checks tenant isolation: accessing another merchant's product returns 403.
    """
    # Check if product exists under this merchant
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.merchant_id == current_user.merchant_id
        )
    )
    product = result.scalar_one_or_none()

    if not product:
        # Check if it exists in another merchant to enforce CROSS_TENANT_ACCESS_DENIED
        foreign_check = await db.execute(select(Product).where(Product.id == product_id))
        if foreign_check.scalar_one_or_none():
            raise CleanDeskException(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code=ErrorCode.CROSS_TENANT_ACCESS_DENIED,
                message="Access denied: product belongs to another merchant workspace."
            )
        raise CleanDeskException(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=ErrorCode.NOT_FOUND,
            message=f"Product {product_id} not found."
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(product, field, val)

    await db.commit()
    await db.refresh(product)

    # Invalidate cache
    cache_service = CacheService(redis_client)
    await cache_service.invalidate_merchant_cache(current_user.merchant_id)

    resp = _to_product_response(product)

    # Real-time WebSocket broadcast
    await ws_manager.broadcast_to_merchant(
        merchant_id=current_user.merchant_id,
        event_type=WebSocketEventType.STOCK_UPDATED,
        data=resp.model_dump(mode="json")
    )

    return resp


@router.post("/bulk-update")
async def bulk_update_products(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Accepts a JSON array, JSON object with 'items', or CSV upload of SKU price/stock updates.
    Processes atomically in a single database transaction.
    Rolls back completely if any single item has invalid/negative values or nonexistent SKU.
    """
    updates_to_process: List[ProductBulkItem] = []
    content_type = request.headers.get("content-type", "")

    # 1. Parse CSV if multipart form upload
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file:
            raise CleanDeskException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_BULK_PAYLOAD,
                message="No CSV file provided in multipart form upload."
            )
        content = await file.read()
        decoded = content.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(decoded))
        for row in csv_reader:
            sku = row.get("sku", "").strip()
            price_raw = row.get("unit_price")
            stock_raw = row.get("stock_quantity")

            if not sku:
                raise CleanDeskException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_code=ErrorCode.INVALID_BULK_PAYLOAD,
                    message="CSV contains row missing 'sku'."
                )

            try:
                price = float(price_raw) if price_raw not in (None, "") else None
                stock = int(stock_raw) if stock_raw not in (None, "") else None
            except ValueError:
                raise CleanDeskException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_code=ErrorCode.INVALID_BULK_PAYLOAD,
                    message=f"Invalid numeric value in CSV for SKU '{sku}'."
                )

            if (stock is not None and stock < 0) or (price is not None and price < 0):
                raise CleanDeskException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_code=ErrorCode.INVALID_BULK_PAYLOAD,
                    message=f"Negative stock or price not allowed for SKU '{sku}'."
                )

            updates_to_process.append(ProductBulkItem(sku=sku, unit_price=price, stock_quantity=stock))

    # 2. Parse JSON body (list or dict with items)
    else:
        try:
            body = await request.json()
        except Exception:
            raise CleanDeskException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_BULK_PAYLOAD,
                message="No bulk update payload provided (expected JSON items or CSV file)."
            )

        raw_items = body if isinstance(body, list) else body.get("items", []) if isinstance(body, dict) else []
        if not raw_items:
            raise CleanDeskException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_BULK_PAYLOAD,
                message="No bulk update payload provided (expected JSON items or CSV file)."
            )

        for item in raw_items:
            try:
                updates_to_process.append(ProductBulkItem(**item))
            except Exception as e:
                raise CleanDeskException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_code=ErrorCode.INVALID_BULK_PAYLOAD,
                    message=f"Invalid item payload: {str(e)}"
                )

    # 3. ATOMIC TRANSACTION: Process all updates
    # If any single item fails or is negative, the whole batch is rolled back
    try:
        async with db.begin_nested():
            for item in updates_to_process:
                if (item.stock_quantity is not None and item.stock_quantity < 0) or \
                   (item.unit_price is not None and item.unit_price < 0):
                    raise CleanDeskException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error_code=ErrorCode.INVALID_BULK_PAYLOAD,
                        message=f"Atomic rollback: SKU '{item.sku}' contains negative values."
                    )

                # Tenant-scoped lookup
                stmt = select(Product).where(
                    Product.merchant_id == current_user.merchant_id,
                    Product.sku == item.sku
                ).with_for_update()  # Lock rows against concurrent writes
                res = await db.execute(stmt)
                product = res.scalar_one_or_none()

                if not product:
                    raise CleanDeskException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error_code=ErrorCode.INVALID_BULK_PAYLOAD,
                        message=f"Atomic rollback: SKU '{item.sku}' does not exist in workspace."
                    )

                if item.unit_price is not None:
                    product.unit_price = item.unit_price
                if item.stock_quantity is not None:
                    product.stock_quantity = item.stock_quantity

        await db.commit()
    except CleanDeskException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise CleanDeskException(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=ErrorCode.INVALID_BULK_PAYLOAD,
            message=f"Bulk transaction failed and was rolled back: {str(exc)}"
        )

    # Invalidate cache after successful atomic commit
    cache_service = CacheService(redis_client)
    await cache_service.invalidate_merchant_cache(current_user.merchant_id)

    # Broadcast update event
    await ws_manager.broadcast_to_merchant(
        merchant_id=current_user.merchant_id,
        event_type=WebSocketEventType.STOCK_UPDATED,
        data={"message": f"Bulk update succeeded for {len(updates_to_process)} products."}
    )

    return {
        "status": "success",
        "updated_count": len(updates_to_process),
        "message": f"Successfully updated {len(updates_to_process)} products atomically."
    }