from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class MerchantRegisterRequest(BaseModel):
    merchant_name: str = Field(..., min_length=2, max_length=255, examples=["Acme Retail"])
    merchant_slug: str = Field(..., min_length=2, max_length=255, examples=["acme-retail"])
    owner_name: str = Field(..., min_length=2, max_length=255, examples=["Dhanrajsinh Parmar"])
    email: EmailStr = Field(..., examples=["owner@acme.com"])
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["owner@acme.com"])
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    id: int
    merchant_id: int
    name: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class MerchantResponse(BaseModel):
    id: int
    name: str
    slug: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    merchant: MerchantResponse


class TokenPayload(BaseModel):
    user_id: int
    merchant_id: int
    role: str
    exp: Optional[int] = None