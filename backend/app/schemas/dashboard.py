from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    total_skus: int
    total_inventory_value: float
    low_stock_count: int
    pending_approvals: int
    from_cache: bool = False