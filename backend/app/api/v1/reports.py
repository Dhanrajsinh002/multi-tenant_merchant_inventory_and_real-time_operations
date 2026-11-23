import csv
import io
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.product import Product
from app.models.user import User

router = APIRouter()


@router.get("/inventory-export")
async def export_inventory_csv(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Streams a downloadable CSV report of the merchant's current inventory valuation
    and low-stock items without buffering the entire table in memory.
    """
    query = select(Product).where(
        Product.merchant_id == current_user.merchant_id
    ).order_by(Product.category, Product.name)

    result = await db.execute(query)
    products = result.scalars().all()

    def iter_csv():
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            "Product ID",
            "SKU",
            "Name",
            "Category",
            "Unit Price ($)",
            "Stock Quantity",
            "Low Stock Threshold",
            "Inventory Valuation ($)",
            "Is Low Stock",
            "Last Updated (UTC)"
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        # Write rows
        for p in products:
            valuation = round(p.stock_quantity * p.unit_price, 2)
            is_low = "YES" if p.stock_quantity <= p.low_stock_threshold else "NO"
            writer.writerow([
                p.id,
                p.sku,
                p.name,
                p.category,
                f"{p.unit_price:.2f}",
                p.stock_quantity,
                p.low_stock_threshold,
                f"{valuation:.2f}",
                is_low,
                p.updated_at.isoformat() if p.updated_at else ""
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    filename = f"inventory_report_merchant_{current_user.merchant_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )