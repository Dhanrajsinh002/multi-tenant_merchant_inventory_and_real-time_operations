from datetime import datetime
from enum import Enum
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base

class UserRole(str, Enum):
    OWNER = "OWNER"
    STAFF = "STAFF"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    merchnat_id = Column(Integer, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255),nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default=UserRole.STAFF.value, nullable=False)
    create_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    merchant = relationship("Merchant", back_populate="users")
