from datetime import datetime
from enum import Enum
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base

class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class StockApprovalRequest(Base):
    __tablename__ = "stock_approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    quantity_delta = Column(Integer, nullable=False)  # Positive for stock increase, negative for deduction
    reason = Column(String(500), nullable=False)
    status = Column(String(50), default=ApprovalStatus.PENDING.value, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    merchant = relationship("Merchant", back_populates="approval_requests")
    product = relationship("Product", back_populates="approvals")
    requester = relationship("User", foreign_keys=[requested_by])
    approver = relationship("User", foreign_keys=[approved_by])

    __table_args__ = (
        # Required Composite Index: (merchant_id, status)
        # Specially requested for fast filtering requests
        Index("ix_approvals_merchant_status", "merchant_id", "status")
    )
