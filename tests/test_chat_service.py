import pytest


def test_chat_success(client):
    """Happy path: valid token, valid query returns 200 with response."""
    resp = client.post(
        "/api/chat",
        json={"query": "How many items are in stock?"},
        headers={"Authorization": "Bearer valid-token", "tenant_id": "1"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "response" in data
    assert "session_id" in data
    assert data["response"] == "Test response from agent"


def test_missing_auth_header(client):
    """No Authorization header -> 401."""
    resp = client.post("/api/chat", json={"query": "test"})
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Unauthorized"


def test_invalid_bearer_format(client):
    """Authorization header without Bearer prefix -> 401."""
    resp = client.post(
        "/api/chat",
        json={"query": "test"},
        headers={"Authorization": "Basic abc123"},
    )
    assert resp.status_code == 401


def test_missing_tenant_id(client):
    """Missing tenant_id header -> 400."""
    resp = client.post(
        "/api/chat",
        json={"query": "test"},
        headers={"Authorization": "Bearer valid-token"},
    )
    assert resp.status_code == 400
    assert "tenant_id" in resp.get_json()["error"].lower()


def test_invalid_token(client):
    """IMS returns None for bad token -> 401."""
    resp = client.post(
        "/api/chat",
        json={"query": "test"},
        headers={"Authorization": "Bearer bad-token", "tenant_id": "1"},
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Unauthorized"


def test_empty_query(client):
    """Empty query -> 400."""
    resp = client.post(
        "/api/chat",
        json={"query": ""},
        headers={"Authorization": "Bearer valid-token", "tenant_id": "1"},
    )
    assert resp.status_code == 400
    assert "empty" in resp.get_json()["error"].lower()


def test_whitespace_only_query(client):
    """Whitespace-only query -> 400."""
    resp = client.post(
        "/api/chat",
        json={"query": "   "},
        headers={"Authorization": "Bearer valid-token", "tenant_id": "1"},
    )
    assert resp.status_code == 400


def test_missing_query_field(client):
    """Missing query field -> 400."""
    resp = client.post(
        "/api/chat",
        json={},
        headers={"Authorization": "Bearer valid-token", "tenant_id": "1"},
    )
    assert resp.status_code == 400


def test_query_trimmed_to_max_length(client):
    """Query over 200 chars is trimmed (not rejected) per app.py implementation."""
    long_query = "A" * 300
    resp = client.post(
        "/api/chat",
        json={"query": long_query},
        headers={"Authorization": "Bearer valid-token", "tenant_id": "1"},
    )
    assert resp.status_code == 200


def test_rate_limit(client):
    """4th request from same token within 60s -> 429."""
    headers = {"Authorization": "Bearer rate-limit-token", "tenant_id": "1"}
    query = {"query": "test query"}

    for i in range(3):
        resp = client.post("/api/chat", json=query, headers=headers)
        assert resp.status_code == 200, f"Request {i+1} failed unexpectedly"

    # 4th request should be rate limited
    resp = client.post("/api/chat", json=query, headers=headers)
    assert resp.status_code == 429
    assert "rate limit" in resp.get_json()["error"].lower()


def test_session_continuity(client):
    """Two requests return consistent session_id if provided."""
    headers = {"Authorization": "Bearer valid-token", "tenant_id": "1"}

    resp1 = client.post("/api/chat", json={"query": "first question"}, headers=headers)
    assert resp1.status_code == 200
    session_id = resp1.get_json()["session_id"]
    assert session_id

    resp2 = client.post(
        "/api/chat",
        json={"query": "follow up question", "session_id": session_id},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.get_json()["session_id"] == session_id


def test_response_has_required_fields(client):
    """Response always includes 'response' and 'session_id'."""
    resp = client.post(
        "/api/chat",
        json={"query": "What is Nobious?"},
        headers={"Authorization": "Bearer valid-token", "tenant_id": "1"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "response" in data
    assert "session_id" in data
    assert isinstance(data["response"], str)
    assert isinstance(data["session_id"], str)
