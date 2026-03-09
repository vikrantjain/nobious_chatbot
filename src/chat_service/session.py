import time
import uuid
from collections import defaultdict
from threading import Lock
from typing import Any


class SessionStore:
    """In-memory session store with rate limiting for chat sessions."""

    def __init__(self, max_messages: int = 3, rate_limit: int = 3, window_seconds: int = 60):
        self._sessions: dict[str, dict[str, Any]] = {}
        self._request_times: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()
        self._max_messages = max_messages
        self._rate_limit = rate_limit
        self._window_seconds = window_seconds

    def get_or_create_session(self, session_id: str | None = None) -> str:
        """Get existing session ID or create a new one."""
        if session_id is None or session_id not in self._sessions:
            session_id = str(uuid.uuid4())
            self._sessions[session_id] = {"messages": [], "summary": ""}
        return session_id

    def get_context(self, session_id: str) -> dict[str, Any]:
        """Get session context (messages + summary)."""
        if session_id not in self._sessions:
            return {"messages": [], "summary": ""}
        return self._sessions[session_id].copy()

    def update_session(self, session_id: str, user_msg: str, assistant_msg: str, summary: str = "") -> None:
        """Update session with new messages. Keeps only last max_messages pairs."""
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = {"messages": [], "summary": ""}
            session = self._sessions[session_id]
            session["messages"].append({"role": "user", "content": user_msg})
            session["messages"].append({"role": "assistant", "content": assistant_msg})
            if len(session["messages"]) > self._max_messages * 2:
                session["messages"] = session["messages"][-(self._max_messages * 2):]
            if summary:
                session["summary"] = summary

    def check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limit. Returns True if allowed, False if exceeded."""
        with self._lock:
            now = time.time()
            times = self._request_times[user_id]
            times = [t for t in times if now - t < self._window_seconds]
            self._request_times[user_id] = times
            if len(times) >= self._rate_limit:
                return False
            times.append(now)
            return True

    def reset(self) -> None:
        """Clear all sessions and rate-limit state. Intended for use in tests."""
        with self._lock:
            self._sessions.clear()
            self._request_times.clear()

    def clear_session(self, session_id: str) -> None:
        """Clear a session."""
        with self._lock:
            self._sessions.pop(session_id, None)
