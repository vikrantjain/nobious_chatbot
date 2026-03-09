import base64
import json
import logging

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


def _decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without signature verification."""
    try:
        payload_b64 = token.split(".")[1]
        # Pad to a multiple of 4 for base64 decoding
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as e:
        logger.warning(f"Failed to decode JWT payload: {e}")
        return {}


def validate_token(token: str) -> dict | None:
    """Decode JWT and extract user info. Returns None if token is invalid."""
    try:
        claims = _decode_jwt_payload(token)
        user_id = claims.get("user_id")
        tenant_id = claims.get("tenant_id")
        if not user_id or not tenant_id:
            return None
        return {
            "id": user_id,
            "username": claims.get("sub"),
            "tenant_id": str(tenant_id),
        }
    except Exception as e:
        logger.error(f"Token decode error: {e}")
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

        # 2. Validate token with IMS (tenant_id and user_id extracted from JWT claims)
        user_info = validate_token(token)
        if not user_info:
            return jsonify({"error": "Unauthorized"}), 401

        user_id = str(user_info["id"])
        tenant_id = str(user_info["tenant_id"])

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
