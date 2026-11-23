from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base

class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(2550), unique=True, index=True, nullable=False)
    status = Column(String(255), default="ACTIVE", nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # Relationships
    users = relationship("User", back_populates="merchant", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="merchant", cascade="all, delete-orphan")
    approval_requests = relationship("StockApprovalRequest", back_populates="merchant", cascade="all, delete-orphan")
