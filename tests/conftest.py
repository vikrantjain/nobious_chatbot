import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_validate_token(monkeypatch):
    """Mock IMS token validation to return a test user."""
    def _validate(token: str):
        if token == "bad-token":
            return None
        return {"id": "test-user-123", "username": "testuser", "tenant_id": "1"}

    monkeypatch.setattr("src.chat_service.app.validate_token", _validate)
    return _validate


@pytest.fixture
def mock_agent_invoke(monkeypatch):
    """Mock agent.invoke() to return a canned response."""
    mock = MagicMock(return_value={
        "response": "Test response from agent",
        "messages": [],
        "error": None,
    })

    class MockAgent:
        def invoke(self, state, config=None):
            return mock(state)

    monkeypatch.setattr("src.chat_service.app.get_agent", lambda: MockAgent())
    return mock


@pytest.fixture
def app(mock_validate_token, mock_agent_invoke):
    """Flask test app with all external dependencies mocked."""
    from src.chat_service.app import create_app, session_store
    flask_app = create_app()
    flask_app.config["TESTING"] = True

    # Reset session store state between tests
    session_store.reset()

    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()
