import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_rate_limiting_exceeded(client: AsyncClient):
    """
    CleanDesk Scenario 4:
    Exceeding login attempts returns 429 Too Many Requests with RATE_LIMIT_EXCEEDED.
    """
    target_email = "target@victim.com"

    # Register user first
    await client.post("/auth/register", json={
        "merchant_name": "Target Store",
        "merchant_slug": "target-store",
        "owner_name": "Target User",
        "email": target_email,
        "password": "CorrectPassword123!"
    })

    # Perform 5 failed login attempts with wrong password
    for i in range(5):
        res = await client.post("/auth/login", json={
            "email": target_email,
            "password": f"WrongPassword_{i}"
        })
        assert res.status_code == 401

    # 6th attempt must be blocked by the rate limiter with 429
    sixth_attempt = await client.post("/auth/login", json={
        "email": target_email,
        "password": "WrongPassword_6"
    })
    assert sixth_attempt.status_code == 429
    err_detail = sixth_attempt.json()
    assert err_detail["error_code"] == "RATE_LIMIT_EXCEEDED"