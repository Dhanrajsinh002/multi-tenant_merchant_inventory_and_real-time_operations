from enum import Enum
from typing import Any, Dict, Optional
from fastapi import HTTPException

class ErrorCode(str, Enum):
    CROSS_TENANT_ACCESS_DENIED = "CROSS_TENANT_ACCESS_DENIED"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
    DUPLICATE_SKU = "DUPLICATE_SKU"
    INVALID_BULK_PAYLOAD = "INVALID_BULK_PAYLOAD"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    UNAUTHORIZED_ROLE = "UNAUTHORIZED_ROLE"
    NOT_FOUND = "NOT_FOUND"

class CleanDeskException(HTTPException):
    def __init__(self, status_code: int, error_code: ErrorCode, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status_code,
            detail={
                "error_code": error_code.value,
                "message": message,
                "details": details or {}
            }
        )
