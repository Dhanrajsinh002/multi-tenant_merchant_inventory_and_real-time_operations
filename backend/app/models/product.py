from datetime import datetime
from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    unit_price = Column(Float, nullable=False)
    stock_quantity = Column(Integer, nullable=False, default=0)
    low_stock_threshold = Column(Integer, nullable=False, default=10)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    merchant = relationship("Merchant", back_populates="products")
    approvals = relationship("StockApprovalRequest", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        # 1. Tenant-scoped uniqueness: SKU is unique per merchant, NOT globally across merchants
        UniqueConstraint("merchant_id", "sku", name="uq_merchant_sku"),
        
        # 2. Composite index for fast tenant SKU lookup during bulk updates
        Index("ix_products_merchant_sku", "merchant_id", "sku"),

        # 3. Composite index for category filtering scoped to merchant
        Index("ix_products_merchant_category", "merchant_id", "category"),

        # 4. Composite index for low-stock metric queries:
        # (WHERE merchant_id = ? AND stock_quantity <= low_stock_threshold)
        Index("ix_products_merchant_low_stock", "merchant_id", "stock_quantity", "low_stock_threshold"),

        # 5. Database-level safeguard to prevent negative inventory    
        CheckConstraint("stock_quantity >= 0", name="chk_stock_quantity_non_negative"),
        CheckConstraint("unit_price >= 0", name="chk_unit_price_non_negative")
    )
