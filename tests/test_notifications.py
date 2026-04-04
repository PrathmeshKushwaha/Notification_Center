import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["app"] == "PulseNotify"


@pytest.mark.asyncio
async def test_create_template(client):
    response = await client.post("/templates", json={
        "name": "test_template",
        "channel": "email",
        "subject": "Hello {{ name }}",
        "body": "<p>Hello {{ name }}</p>"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test_template"
    assert data["channel"] == "email"
    assert "id" in data
    return data["id"]


@pytest.mark.asyncio
async def test_send_notification_queued(client):
    with patch("app.workers.email_worker.deliver_email.apply_async"):
        response = await client.post("/notify", json={
            "user_id": "test-user-001",
            "channel": "email",
            "priority": "normal",
            "variables": {"name": "Test"},
            "idempotency_key": "test-idem-001"
        })
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "queued"
        assert data["user_id"] == "test-user-001"
        assert data["channel"] == "email"
        assert "id" in data


@pytest.mark.asyncio
async def test_idempotency(client):
    with patch("app.workers.email_worker.deliver_email.apply_async"):
        payload = {
            "user_id": "test-user-002",
            "channel": "email",
            "priority": "normal",
            "variables": {"name": "Test"},
            "idempotency_key": "test-idem-unique-001"
        }
        response1 = await client.post("/notify", json=payload)
        response2 = await client.post("/notify", json=payload)

        assert response1.status_code == 202
        assert response2.status_code == 202
        assert response1.json()["id"] == response2.json()["id"]


@pytest.mark.asyncio
async def test_notification_status(client):
    with patch("app.workers.email_worker.deliver_email.apply_async"):
        response = await client.post("/notify", json={
            "user_id": "test-user-003",
            "channel": "email",
            "priority": "normal",
            "variables": {"name": "Test"},
            "idempotency_key": "test-idem-status-001"
        })
        assert response.status_code == 202
        notification_id = response.json()["id"]

    status_response = await client.get(f"/notify/{notification_id}/status")
    assert status_response.status_code == 200
    data = status_response.json()
    assert data["id"] == notification_id
    assert data["status"] in ["queued", "pending", "delivered", "failed"]


@pytest.mark.asyncio
async def test_set_preferences(client):
    response = await client.put("/preferences/test-user-001", json={
        "email_enabled": True,
        "websocket_enabled": True,
        "webhook_enabled": False,
        "timezone": "Asia/Kolkata"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email_enabled"] is True
    assert data["timezone"] == "Asia/Kolkata"
    assert data["webhook_enabled"] is False


@pytest.mark.asyncio
async def test_disabled_channel_rejected(client):
    await client.put("/preferences/test-user-004", json={
        "email_enabled": False,
        "websocket_enabled": True,
        "webhook_enabled": False,
    })

    with patch("app.workers.email_worker.deliver_email.apply_async"):
        response = await client.post("/notify", json={
            "user_id": "test-user-004",
            "channel": "email",
            "priority": "normal",
            "variables": {},
            "idempotency_key": "test-disabled-001"
        })
        assert response.status_code == 400
        assert "disabled" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_dlq_empty(client):
    response = await client.get("/dlq")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_notification_history(client):
    response = await client.get("/notify/history?user_id=test-user-001")
    assert response.status_code == 200
    assert isinstance(response.json(), list)