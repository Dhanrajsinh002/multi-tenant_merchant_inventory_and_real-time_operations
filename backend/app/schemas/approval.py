from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.models.approval import ApprovalStatus


class ApprovalCreate(BaseModel):
    product_id: int
    quantity_delta: int = Field(..., examples=[25])
    reason: str = Field(..., min_length=3, max_length=500, examples=["Supplier restock shipment received"])

    @field_validator("quantity_delta")
    @classmethod
    def non_zero_delta(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Stock adjustment quantity_delta cannot be zero")
        return v


class ApprovalDecision(BaseModel):
    status: ApprovalStatus = Field(..., examples=[ApprovalStatus.APPROVED])


class ApprovalResponse(BaseModel):
    id: int
    merchant_id: int
    product_id: int
    product_sku: Optional[str] = None
    product_name: Optional[str] = None
    requested_by: int
    requester_name: Optional[str] = None
    approved_by: Optional[int] = None
    approver_name: Optional[str] = None
    quantity_delta: int
    reason: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True