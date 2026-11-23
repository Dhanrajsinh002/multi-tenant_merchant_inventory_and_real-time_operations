import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_staff_user_blocked_from_approving(client: AsyncClient, db_session: AsyncSession):
    """
    CleanDesk Scenario 5:
    A STAFF user is blocked (403 UNAUTHORIZED_ROLE) from approving their own stock request.
    Only OWNER can approve.
    """
    # 1. Register Merchant workspace (creates OWNER user)
    owner_reg = await client.post("/auth/register", json={
        "merchant_name": "RBAC Store",
        "merchant_slug": "rbac-store",
        "owner_name": "Oliver Owner",
        "email": "oliver@rbac.com",
        "password": "Password123!"
    })
    assert owner_reg.status_code == 201
    owner_data = owner_reg.json()
    merchant_id = owner_data["merchant"]["id"]
    owner_token = owner_data["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # 2. Add product as Owner
    prod_res = await client.post("/products", headers=owner_headers, json={
        "sku": "RBAC-PROD-1",
        "name": "RBAC Item",
        "category": "Office",
        "unit_price": 25.0,
        "stock_quantity": 10,
        "low_stock_threshold": 5
    })
    assert prod_res.status_code == 201
    product_id = prod_res.json()["id"]

    # 3. Create a STAFF user directly within the same merchant workspace
    staff_user = User(
        merchant_id=merchant_id,
        name="Sam Staff",
        email="sam@rbac.com",
        password_hash=get_password_hash("StaffPass123!"),
        role=UserRole.STAFF.value
    )
    db_session.add(staff_user)
    await db_session.commit()
    await db_session.refresh(staff_user)

    staff_token = create_access_token(
        user_id=staff_user.id,
        merchant_id=merchant_id,
        role=UserRole.STAFF.value
    )
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # 4. STAFF user requests a stock adjustment -> SUCESSS (201)
    req_res = await client.post("/approvals", headers=staff_headers, json={
        "product_id": product_id,
        "quantity_delta": 5,
        "reason": "Restocking shelves"
    })
    assert req_res.status_code == 201
    approval_id = req_res.json()["id"]

    # 5. STAFF attempts to approve their own request -> MUST BE BLOCKED (403 UNAUTHORIZED_ROLE)
    staff_decision = await client.post(
        f"/approvals/{approval_id}/decision",
        headers=staff_headers,
        json={"status": "APPROVED"}
    )
    assert staff_decision.status_code == 403
    assert staff_decision.json()["error_code"] == "UNAUTHORIZED_ROLE"

    # 6. OWNER approves the request -> MUST SUCCEED (200)
    owner_decision = await client.post(
        f"/approvals/{approval_id}/decision",
        headers=owner_headers,
        json={"status": "APPROVED"}
    )
    assert owner_decision.status_code == 200
    assert owner_decision.json()["status"] == "APPROVED"