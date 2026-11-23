import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cache_aside_and_explicit_invalidation(client: AsyncClient):
    """
    CleanDesk Scenario 3:
    Verify cache hit on repeated dashboard reads and cache invalidation after an approval decision.
    """
    # 1. Register merchant
    reg_res = await client.post("/auth/register", json={
        "merchant_name": "Cache Test Store",
        "merchant_slug": "cache-test-store",
        "owner_name": "Chris Owner",
        "email": "chris@cachetest.com",
        "password": "Password123!"
    })
    assert reg_res.status_code == 201
    headers = {"Authorization": f"Bearer {reg_res.json()['access_token']}"}

    # 2. Add an initial product (stock: 10, price: $50)
    prod_res = await client.post("/products", headers=headers, json={
        "sku": "CACHE-001",
        "name": "Cached Monitor",
        "category": "Electronics",
        "unit_price": 50.0,
        "stock_quantity": 10,
        "low_stock_threshold": 5
    })
    assert prod_res.status_code == 201
    product_id = prod_res.json()["id"]

    # 3. First read: Cache Miss -> Populates cache from PostgreSQL
    first_read = await client.get("/dashboard/metrics", headers=headers)
    assert first_read.status_code == 200
    data_first = first_read.json()
    assert data_first["from_cache"] is False
    assert data_first["total_inventory_value"] == 500.0

    # 4. Second read: Cache Hit -> Served directly from Redis
    second_read = await client.get("/dashboard/metrics", headers=headers)
    assert second_read.status_code == 200
    data_second = second_read.json()
    assert data_second["from_cache"] is True
    assert data_second["total_inventory_value"] == 500.0

    # 5. Create a stock approval request to add +10 items ($500 -> $1000)
    req_res = await client.post("/approvals", headers=headers, json={
        "product_id": product_id,
        "quantity_delta": 10,
        "reason": "Restock batch"
    })
    assert req_res.status_code == 201
    approval_id = req_res.json()["id"]

    # 6. Execute approval decision (triggers explicit cache invalidation!)
    decision_res = await client.post(
        f"/approvals/{approval_id}/decision",
        headers=headers,
        json={"status": "APPROVED"}
    )
    assert decision_res.status_code == 200

    # 7. Third read: Must be a Cache Miss because cache was invalidated,
    # and must reflect the updated inventory valuation ($1000.0)
    third_read = await client.get("/dashboard/metrics", headers=headers)
    assert third_read.status_code == 200
    data_third = third_read.json()
    assert data_third["from_cache"] is False
    assert data_third["total_inventory_value"] == 1000.0