import logging

import httpx
from flask import Flask, request, jsonify

from src.chat_service.config import config
from src.chat_service.session import SessionStore
from src.chat_service.agent import create_agent, build_context_messages, SERVICE_UNAVAILABLE_MSG
from src.chat_service.account_tools import ACCOUNT_TOOLS
from src.chat_service.doc_tools import DOC_TOOLS

logger = logging.getLogger(__name__)

session_store = SessionStore(
    rate_limit=config.rate_limit_per_min,
    window_seconds=60,
)

_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent(ACCOUNT_TOOLS, DOC_TOOLS)
    return _agent


def validate_token(token: str, tenant_id: str) -> dict | None:
    """Validate Bearer token against IMS by calling an authenticated endpoint.

    Uses the company list endpoint as a lightweight auth check — returns a
    minimal user dict on success, None on failure.
    """
    try:
        with httpx.Client(verify=False, timeout=5.0) as client:
            r = client.get(
                f"{config.ims_auth_url}/api/vista/company/allcompanies",
                headers={
                    "Authorization": f"Bearer {token}",
                    "login-type": "NATIVE",
                    "tenant_id": tenant_id,
                },
            )
            if r.status_code == 200:
                return {"token": token}
            return None
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return None


def create_app() -> Flask:
    app = Flask(__name__)

    logging.basicConfig(level=logging.INFO)

    @app.post("/api/chat")
    def chat():
        # 1. Extract Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401
        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            return jsonify({"error": "Unauthorized"}), 401

        # 2. Extract tenant_id (required)
        # Flask/Werkzeug normalizes header names (underscore → hyphen), so check both forms
        tenant_id = (request.headers.get("tenant-id") or request.headers.get("tenant_id") or "").strip()
        if not tenant_id:
            return jsonify({"error": "tenant_id header is required"}), 400

        # 3. Validate token with IMS
        user_info = validate_token(token, tenant_id)
        if not user_info:
            return jsonify({"error": "Unauthorized"}), 401

        user_id = str(
            user_info.get("id")
            or user_info.get("userId")
            or user_info.get("sub")
            or token[:16]
        )

        # 4. Rate limit
        if not session_store.check_rate_limit(user_id):
            return jsonify({"error": "Rate limit exceeded. Please wait before sending another message."}), 429

        # 5. Validate query
        data = request.get_json(silent=True) or {}
        query = (data.get("query") or "").strip()
        if not query:
            return jsonify({"error": "Query cannot be empty"}), 400

        query = query[:config.max_query_length]

        # 6. Session management (session_id used as graph thread_id for MemorySaver)
        session_id = data.get("session_id")
        session_id = session_store.get_or_create_session(session_id)

        # 7. Build messages for current query
        messages = build_context_messages(query)

        # 8. Invoke agent (history maintained by graph checkpointer keyed on thread_id)
        try:
            agent = get_agent()
            result = agent.invoke(
                {
                    "messages": messages,
                    "access_token": token,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "response": "",
                    "error": None,
                },
                config={"configurable": {"thread_id": session_id}},
            )
            response_text = result.get("response") or ""
            if not response_text and result.get("messages"):
                last_msg = result["messages"][-1]
                response_text = getattr(last_msg, "content", str(last_msg))
            if result.get("error"):
                response_text = result["error"]
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return jsonify({"error": SERVICE_UNAVAILABLE_MSG}), 500

        return jsonify({"response": response_text, "session_id": session_id})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
