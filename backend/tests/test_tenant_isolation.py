import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_tenant_isolation_products_and_approvals(client: AsyncClient):
    """
    CleanDesk Scenario 1:
    Merchant A cannot read, update, or approve Merchant B's products or requests.
    Cross-tenant access must return 403 Forbidden.
    """
    # 1. Register Merchant A
    res_a = await client.post("/auth/register", json={
        "merchant_name": "Alpha Corp",
        "merchant_slug": "alpha-corp",
        "owner_name": "Alice Owner",
        "email": "alice@alpha.com",
        "password": "Password123!"
    })
    assert res_a.status_code == 201
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Register Merchant B
    res_b = await client.post("/auth/register", json={
        "merchant_name": "Beta Retail",
        "merchant_slug": "beta-retail",
        "owner_name": "Bob Owner",
        "email": "bob@beta.com",
        "password": "Password123!"
    })
    assert res_b.status_code == 201
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. Merchant A creates a product
    prod_res = await client.post("/products", headers=headers_a, json={
        "sku": "ALPHA-001",
        "name": "Alpha Widget",
        "category": "Widgets",
        "unit_price": 49.99,
        "stock_quantity": 100,
        "low_stock_threshold": 15
    })
    assert prod_res.status_code == 201
    product_a_id = prod_res.json()["id"]

    # 4. Merchant B attempts to UPDATE Merchant A's product -> MUST return 403
    cross_update = await client.put(f"/products/{product_a_id}", headers=headers_b, json={
        "name": "Hacked Name"
    })
    assert cross_update.status_code == 403
    assert cross_update.json()["error_code"] == "CROSS_TENANT_ACCESS_DENIED"

    # 5. Merchant A creates a stock approval request
    approval_req = await client.post("/approvals", headers=headers_a, json={
        "product_id": product_a_id,
        "quantity_delta": 20,
        "reason": "Restock shipment"
    })
    assert approval_req.status_code == 201
    approval_a_id = approval_req.json()["id"]

    # 6. Merchant B attempts to APPROVE Merchant A's request -> MUST return 403
    cross_approve = await client.post(
        f"/approvals/{approval_a_id}/decision",
        headers=headers_b,
        json={"status": "APPROVED"}
    )
    assert cross_approve.status_code == 403
    assert cross_approve.json()["error_code"] == "CROSS_TENANT_ACCESS_DENIED"