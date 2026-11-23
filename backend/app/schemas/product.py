from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ProductBase(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100, examples=["SKU-1001"])
    name: str = Field(..., min_length=1, max_length=255, examples=["Mechanical Keyboard"])
    category: str = Field(..., min_length=1, max_length=100, examples=["Electronics"])
    unit_price: float = Field(..., ge=0, examples=[89.99])
    stock_quantity: int = Field(default=0, ge=0, examples=[50])
    low_stock_threshold: int = Field(default=10, ge=0, examples=[10])


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    unit_price: Optional[float] = Field(None, ge=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    low_stock_threshold: Optional[int] = Field(None, ge=0)


class ProductBulkItem(BaseModel):
    sku: str = Field(..., min_length=1)
    unit_price: Optional[float] = Field(None, ge=0)
    stock_quantity: Optional[int] = Field(None, ge=0)

    @field_validator("stock_quantity", "unit_price")
    @classmethod
    def validate_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Value must be non-negative")
        return v


class ProductResponse(ProductBase):
    id: int
    merchant_id: int
    is_low_stock: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedProductsResponse(BaseModel):
    items: List[ProductResponse]
    total: int
    page: int
    size: int
    pages: int