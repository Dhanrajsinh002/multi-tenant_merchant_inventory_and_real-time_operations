import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_atomic_bulk_update_rollback(client: AsyncClient):
    """
    CleanDesk Scenario 2:
    If 1 item in a 5-item bulk update has an invalid/negative value,
    none of the 5 products are modified.
    """
    # 1. Register merchant
    reg_res = await client.post("/auth/register", json={
        "merchant_name": "Rollback Store",
        "merchant_slug": "rollback-store",
        "owner_name": "Robert Owner",
        "email": "robert@rollback.com",
        "password": "Password123!"
    })
    assert reg_res.status_code == 201
    headers = {"Authorization": f"Bearer {reg_res.json()['access_token']}"}

    # 2. Seed 5 initial products (initial stock = 10, unit_price = 100.0)
    initial_skus = [f"BULK-{i}" for i in range(1, 6)]
    for sku in initial_skus:
        p = await client.post("/products", headers=headers, json={
            "sku": sku,
            "name": f"Item {sku}",
            "category": "Testing",
            "unit_price": 100.0,
            "stock_quantity": 10,
            "low_stock_threshold": 5
        })
        assert p.status_code == 201

    # 3. Attempt a 5-item bulk update where the 4th item has negative stock
    bulk_payload = [
        {"sku": "BULK-1", "stock_quantity": 50, "unit_price": 120.0},
        {"sku": "BULK-2", "stock_quantity": 60, "unit_price": 130.0},
        {"sku": "BULK-3", "stock_quantity": 70, "unit_price": 140.0},
        {"sku": "BULK-4", "stock_quantity": -99, "unit_price": 150.0},  # INVALID!
        {"sku": "BULK-5", "stock_quantity": 80, "unit_price": 160.0},
    ]

    bulk_res = await client.post("/products/bulk-update", headers=headers, json=bulk_payload)
    assert bulk_res.status_code in (400, 422)  # Fails with Bad Request / Validation error

    # 4. Verify Atomic Rollback: Verify NONE of the products were modified
    catalog = await client.get("/products", headers=headers)
    assert catalog.status_code == 200
    items = {item["sku"]: item for item in catalog.json()["items"]}

    for sku in initial_skus:
        assert items[sku]["stock_quantity"] == 10, f"Stock changed for {sku} despite rollback!"
        assert items[sku]["unit_price"] == 100.0, f"Price changed for {sku} despite rollback!"