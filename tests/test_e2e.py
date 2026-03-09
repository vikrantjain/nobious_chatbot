"""
End-to-end tests for the LangGraph agent pipeline.

Strategy:
- Real LangGraph graph compiled with MemorySaver (no MockAgent shortcut)
- Lightweight fake tool functions (in-process stubs, no IMS/AWS calls)
- LLM mocked via `init_chat_model` patch — FakeLLM controls routing decisions
  and tool-call / direct-answer responses
- Full Flask → session_store → agent → tools path exercised in TestFlaskE2E
"""

import pytest
from typing import Annotated
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import InjectedToolArg, tool as lc_tool

from src.chat_service.agent import (
    create_agent,
    ChatStructure,
    QueryType,
)


# ---------------------------------------------------------------------------
# Spy-backed fake tool functions
# (spies let us assert call args without mocking the whole tool layer)
# ---------------------------------------------------------------------------

_company_spy = MagicMock(return_value={"companies": [{"name": "Acme Corp", "code": "001"}]})
_docs_spy = MagicMock(
    return_value=[{"rank": 1, "score": 0.9, "text": "IMS manages inventory", "source": "intro.md"}]
)


async def fake_get_all_companies(
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
) -> dict:
    """Return a list of companies for the given tenant."""
    return _company_spy(access_token=access_token, tenant_id=tenant_id)


def fake_search_documentation(query: str, top_k: int = 5) -> list:
    """Search documentation and return relevant chunks."""
    return _docs_spy(query=query, top_k=top_k)


FAKE_ACCOUNT_TOOLS = [lc_tool(fake_get_all_companies)]
FAKE_DOC_TOOLS = [lc_tool(fake_search_documentation)]


# ---------------------------------------------------------------------------
# FakeLLM — substitutes the object returned by init_chat_model()
# ---------------------------------------------------------------------------

class _SeqLLM:
    """Yields responses from a fixed list; repeats the last one if exhausted."""

    def __init__(self, responses: list):
        self._responses = responses
        self._idx = 0

    def invoke(self, messages):
        resp = self._responses[self._idx]
        self._idx = min(self._idx + 1, len(self._responses) - 1)
        return resp


class FakeLLM:
    """
    Drop-in for the object returned by `init_chat_model()`.

    - `with_structured_output()` → _SeqLLM that yields ChatStructure objects
    - `bind_tools()` → distinguished by whether 'search_documentation' appears
      in the bound tool names (doc tools) or not (account tools)
    """

    def __init__(self, chat_responses, account_responses=None, docs_responses=None):
        self._chat = _SeqLLM(chat_responses)
        self._account = _SeqLLM(account_responses or [AIMessage(content="(no response)")])
        self._docs = _SeqLLM(docs_responses or [AIMessage(content="(no response)")])

    def with_structured_output(self, schema):
        return self._chat

    def bind_tools(self, tools):
        names = {t.name for t in tools}
        if any("search_documentation" in n for n in names):
            return self._docs
        return self._account


# ---------------------------------------------------------------------------
# Helper — build a tool_call dict exactly as LangChain expects in AIMessage
# ---------------------------------------------------------------------------

def tool_call(name: str, args: dict, call_id: str = "call_1") -> dict:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_state():
    return {
        "messages": [HumanMessage(content="test query")],
        "access_token": "test-token",
        "tenant_id": "1",
        "user_id": "user-123",
        "response": "",
        "error": None,
    }


@pytest.fixture(autouse=True)
def reset_spies():
    """Reset spy state and side-effects between tests."""
    _company_spy.reset_mock()
    _company_spy.side_effect = None
    _company_spy.return_value = {"companies": [{"name": "Acme Corp", "code": "001"}]}
    _docs_spy.reset_mock()
    _docs_spy.side_effect = None
    _docs_spy.return_value = [
        {"rank": 1, "score": 0.9, "text": "IMS manages inventory", "source": "intro.md"}
    ]


def make_agent(fake_llm: FakeLLM):
    with patch("src.chat_service.agent.init_chat_model", return_value=fake_llm):
        return create_agent(FAKE_ACCOUNT_TOOLS, FAKE_DOC_TOOLS)


# ---------------------------------------------------------------------------
# 1. chat_llm_call routing
# ---------------------------------------------------------------------------

class TestChatLLMRouting:

    def test_clarification_needed_ends_immediately(self, base_state):
        """chat_llm returns clarification_needed=True → response is the clarification, no further nodes."""
        agent = make_agent(FakeLLM(
            chat_responses=[ChatStructure(
                clarification_needed=True,
                clarification_message="Which company are you asking about?",
                query_type=QueryType.none,
            )]
        ))
        result = agent.invoke(base_state, config={"configurable": {"thread_id": "r-1"}})
        assert result["response"] == "Which company are you asking about?"
        assert result["error"] is None

    def test_query_type_none_uses_default_message(self, base_state):
        """query_type=none with empty clarification_message falls back to the default phrase."""
        agent = make_agent(FakeLLM(
            chat_responses=[ChatStructure(
                clarification_needed=False,
                clarification_message="",
                query_type=QueryType.none,
            )]
        ))
        result = agent.invoke(base_state, config={"configurable": {"thread_id": "r-2"}})
        assert result["response"] == "Could you please clarify your question?"
        assert result["error"] is None

    def test_chat_llm_exception_returns_unavailability_message(self, base_state):
        """If chat_llm raises, the graph catches it and returns the standard error message."""

        class _Exploding:
            def invoke(self, messages):
                raise RuntimeError("Bedrock timeout")

        class _FailingLLM:
            def with_structured_output(self, schema):
                return _Exploding()

            def bind_tools(self, tools):
                return _Exploding()

        with patch("src.chat_service.agent.init_chat_model", return_value=_FailingLLM()):
            agent = create_agent(FAKE_ACCOUNT_TOOLS, FAKE_DOC_TOOLS)

        result = agent.invoke(base_state, config={"configurable": {"thread_id": "r-3"}})
        assert "temporarily unavailable" in result["response"].lower()
        assert result["error"] is not None


# ---------------------------------------------------------------------------
# 2. Account query path
# ---------------------------------------------------------------------------

class TestAccountQueryPath:

    def test_direct_response_without_tool_call(self, base_state):
        """Account LLM answers directly (no tool_calls) → response returned immediately."""
        agent = make_agent(FakeLLM(
            chat_responses=[ChatStructure(query_type=QueryType.account_query)],
            account_responses=[AIMessage(content="You have no pending orders.")],
        ))
        result = agent.invoke(base_state, config={"configurable": {"thread_id": "a-1"}})
        assert result["response"] == "You have no pending orders."
        assert result["error"] is None

    def test_tool_call_then_final_response(self, base_state):
        """Account LLM calls a tool, tool executes, LLM produces the final answer."""
        tc = tool_call("fake_get_all_companies", {})
        agent = make_agent(FakeLLM(
            chat_responses=[ChatStructure(query_type=QueryType.account_query)],
            account_responses=[
                AIMessage(content="", tool_calls=[tc]),   # triggers account_tools
                AIMessage(content="You have 1 company: Acme Corp."),
            ],
        ))
        result = agent.invoke(base_state, config={"configurable": {"thread_id": "a-2"}})
        assert result["response"] == "You have 1 company: Acme Corp."
        assert _company_spy.called

    def test_access_token_injected_from_state_not_llm_args(self, base_state):
        """account_tools must inject access_token and tenant_id from AgentState, not from LLM-generated args."""
        base_state["access_token"] = "secret-bearer-token"
        tc = tool_call("fake_get_all_companies", {})  # no access_token or tenant_id in LLM args

        agent = make_agent(FakeLLM(
            chat_responses=[ChatStructure(query_type=QueryType.account_query)],
            account_responses=[
                AIMessage(content="", tool_calls=[tc]),
                AIMessage(content="Done."),
            ],
        ))
        agent.invoke(base_state, config={"configurable": {"thread_id": "a-3"}})

        call_kwargs = _company_spy.call_args[1]
        assert call_kwargs["access_token"] == "secret-bearer-token"
        assert call_kwargs["tenant_id"] == 1

    def test_tool_error_produces_unavailability_tool_message(self, base_state):
        """If a tool raises, account_tools puts the standard error text into a ToolMessage."""
        _company_spy.side_effect = Exception("IMS down")
        tc = tool_call("fake_get_all_companies", {})

        agent = make_agent(FakeLLM(
            chat_responses=[ChatStructure(query_type=QueryType.account_query)],
            account_responses=[
                AIMessage(content="", tool_calls=[tc]),
                AIMessage(content="Handled."),
            ],
        ))
        result = agent.invoke(base_state, config={"configurable": {"thread_id": "a-4"}})

        tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert tool_msgs, "Expected at least one ToolMessage"
        assert any("temporarily unavailable" in m.content.lower() for m in tool_msgs)

    def test_unknown_tool_name_produces_not_available_message(self, base_state):
        """If the LLM requests a tool not in account_tool_map, the graph returns a graceful error."""
        tc = tool_call("nonexistent_tool", {"some_arg": "val"})

        agent = make_agent(FakeLLM(
            chat_responses=[ChatStructure(query_type=QueryType.account_query)],
            account_responses=[
                AIMessage(content="", tool_calls=[tc]),
                AIMessage(content="Noted."),
            ],
        ))
        result = agent.invoke(base_state, config={"configurable": {"thread_id": "a-5"}})

        tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert any("not available" in m.content for m in tool_msgs)

    def test_account_llm_exception_returns_unavailability(self, base_state):
        """If account_llm raises, the node catches it and sets the error response."""

        class _Exploding:
            def invoke(self, messages):
                raise RuntimeError("AWS failure")

        class _PartialFakeLLM(FakeLLM):
            def bind_tools(self, tools):
                names = {t.name for t in tools}
                if any("search_documentation" in n for n in names):
                    return self._docs
                return _Exploding()

        fake_llm = _PartialFakeLLM(
            chat_responses=[ChatStructure(query_type=QueryType.account_query)],
        )
        with patch("src.chat_service.agent.init_chat_model", return_value=fake_llm):
            agent = create_agent(FAKE_ACCOUNT_TOOLS, FAKE_DOC_TOOLS)

        result = agent.invoke(base_state, config={"configurable": {"thread_id": "a-6"}})
        assert "temporarily unavailable" in result["response"].lower()


# ---------------------------------------------------------------------------
# 3. Docs query path
# ---------------------------------------------------------------------------

class TestDocsQueryPath:

    def test_direct_response_without_tool_call(self, base_state):
        """Docs LLM answers without tool calls → response returned immediately."""
        agent = make_agent(FakeLLM(
            chat_responses=[ChatStructure(query_type=QueryType.product_docs_query)],
            docs_responses=[AIMessage(content="Nobious IMS is an inventory management system.")],
        ))
        result = agent.invoke(base_state, config={"configurable": {"thread_id": "d-1"}})
        assert result["response"] == "Nobious IMS is an inventory management system."

    def test_tool_call_then_final_response(self, base_state):
        """Docs LLM calls search_documentation, tool runs, LLM produces final answer."""
        tc = tool_call("fake_search_documentation", {"query": "how does inventory work", "top_k": 3})

        agent = make_agent(FakeLLM(
            chat_responses=[ChatStructure(query_type=QueryType.product_docs_query)],
            docs_responses=[
                AIMessage(content="", tool_calls=[tc]),
                AIMessage(content="Nobious IMS manages inventory across multiple locations."),
            ],
        ))
        result = agent.invoke(base_state, config={"configurable": {"thread_id": "d-2"}})
        assert result["response"] == "Nobious IMS manages inventory across multiple locations."
        assert _docs_spy.called
        assert _docs_spy.call_args[1]["query"] == "how does inventory work"

    def test_docs_tool_error_produces_unavailability_message(self, base_state):
        """If search_documentation raises, docs_tools stores the standard error in a ToolMessage."""
        _docs_spy.side_effect = Exception("BM25S crash")
        tc = tool_call("fake_search_documentation", {"query": "inventory", "top_k": 3})

        agent = make_agent(FakeLLM(
            chat_responses=[ChatStructure(query_type=QueryType.product_docs_query)],
            docs_responses=[
                AIMessage(content="", tool_calls=[tc]),
                AIMessage(content="Handled."),
            ],
        ))
        result = agent.invoke(base_state, config={"configurable": {"thread_id": "d-3"}})

        tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert any("temporarily unavailable" in m.content.lower() for m in tool_msgs)


# ---------------------------------------------------------------------------
# 4. Multi-turn conversation (MemorySaver)
# ---------------------------------------------------------------------------

class TestMultiTurnConversation:

    def test_memory_accumulates_across_turns(self):
        """Two invocations on the same thread_id — the second state should contain both turns' messages."""
        thread_id = "multi-1"
        fake_llm = FakeLLM(
            chat_responses=[
                ChatStructure(query_type=QueryType.account_query),
                ChatStructure(query_type=QueryType.account_query),
            ],
            account_responses=[
                AIMessage(content="Turn 1 answer."),
                AIMessage(content="Turn 2 answer."),
            ],
        )
        agent = make_agent(fake_llm)

        state1 = {
            "messages": [HumanMessage(content="First question")],
            "access_token": "tok", "tenant_id": "1", "user_id": "u1",
            "response": "", "error": None,
        }
        result1 = agent.invoke(state1, config={"configurable": {"thread_id": thread_id}})
        assert result1["response"] == "Turn 1 answer."

        state2 = {
            "messages": [HumanMessage(content="Follow-up question")],
            "access_token": "tok", "tenant_id": "1", "user_id": "u1",
            "response": "", "error": None,
        }
        result2 = agent.invoke(state2, config={"configurable": {"thread_id": thread_id}})
        assert result2["response"] == "Turn 2 answer."

        # MemorySaver accumulates via add_messages — both human turns must be present
        human_msgs = [m for m in result2["messages"] if isinstance(m, HumanMessage)]
        assert len(human_msgs) >= 2, "MemorySaver should retain history from both turns"

    def test_different_thread_ids_are_isolated(self):
        """Agents on different thread_ids must not share conversation state."""
        agent = make_agent(FakeLLM(
            chat_responses=[
                ChatStructure(query_type=QueryType.account_query),
                ChatStructure(query_type=QueryType.account_query),
            ],
            account_responses=[
                AIMessage(content="Session A answer."),
                AIMessage(content="Session B answer."),
            ],
        ))

        state = {
            "messages": [HumanMessage(content="question")],
            "access_token": "t", "tenant_id": "1", "user_id": "u",
            "response": "", "error": None,
        }
        result_a = agent.invoke(state, config={"configurable": {"thread_id": "session-a"}})
        result_b = agent.invoke(state, config={"configurable": {"thread_id": "session-b"}})

        assert result_a["response"] == "Session A answer."
        assert result_b["response"] == "Session B answer."

        # Verify isolation: session-b messages should NOT contain session-a's human message
        b_human_msgs = [m for m in result_b["messages"] if isinstance(m, HumanMessage)]
        assert len(b_human_msgs) == 1, "Session B should have only its own message"


# ---------------------------------------------------------------------------
# 5. Full Flask → agent pipeline (real graph, mocked LLM + token validation)
# ---------------------------------------------------------------------------

class TestFlaskE2EPipeline:
    """
    Exercises the complete request path:
      Flask /api/chat → session_store → get_agent() → real LangGraph graph → fake LLM
    Token validation is mocked at the app boundary (same as conftest fixtures).
    Uses FAKE_ACCOUNT_TOOLS / FAKE_DOC_TOOLS to avoid IMS network calls.
    """

    def _make_client(self, fake_llm: FakeLLM, monkeypatch):
        """Build a Flask test client wired to a real agent using fake_llm."""
        import src.chat_service.app as app_module

        # Reset the agent singleton so the next request creates a fresh one
        app_module._agent = None

        # Patch token validation
        monkeypatch.setattr(
            "src.chat_service.app.validate_token",
            lambda token: {"id": "u1", "tenant_id": "1"} if token != "bad" else None,
        )

        # Build a real agent with the fake LLM and inject it via get_agent()
        with patch("src.chat_service.agent.init_chat_model", return_value=fake_llm):
            real_agent = create_agent(FAKE_ACCOUNT_TOOLS, FAKE_DOC_TOOLS)

        monkeypatch.setattr("src.chat_service.app.get_agent", lambda: real_agent)

        from src.chat_service.app import create_app, session_store
        flask_app = create_app()
        flask_app.config["TESTING"] = True
        session_store._sessions.clear()
        session_store._request_times.clear()

        return flask_app.test_client()

    def test_clarification_response_end_to_end(self, monkeypatch):
        """Full pipeline: valid request → chat_llm needs clarification → 200 with message."""
        fake_llm = FakeLLM(
            chat_responses=[ChatStructure(
                clarification_needed=True,
                clarification_message="Which company are you referring to?",
                query_type=QueryType.none,
            )]
        )
        client = self._make_client(fake_llm, monkeypatch)

        resp = client.post(
            "/api/chat",
            json={"query": "show me data"},
            headers={"Authorization": "Bearer valid-tok", "tenant_id": "1"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["response"] == "Which company are you referring to?"
        assert "session_id" in data

    def test_account_direct_response_end_to_end(self, monkeypatch):
        """Full pipeline: account query answered directly by LLM (no tools)."""
        fake_llm = FakeLLM(
            chat_responses=[ChatStructure(query_type=QueryType.account_query)],
            account_responses=[AIMessage(content="You have 5 open tickets.")],
        )
        client = self._make_client(fake_llm, monkeypatch)

        resp = client.post(
            "/api/chat",
            json={"query": "how many open tickets do I have?"},
            headers={"Authorization": "Bearer valid-tok", "tenant_id": "1"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["response"] == "You have 5 open tickets."

    def test_account_tool_call_end_to_end(self, monkeypatch):
        """Full pipeline: account query → tool called → final LLM answer returned."""
        tc = tool_call("fake_get_all_companies", {})
        fake_llm = FakeLLM(
            chat_responses=[ChatStructure(query_type=QueryType.account_query)],
            account_responses=[
                AIMessage(content="", tool_calls=[tc]),
                AIMessage(content="You have 1 company: Acme Corp."),
            ],
        )
        client = self._make_client(fake_llm, monkeypatch)

        resp = client.post(
            "/api/chat",
            json={"query": "list my companies"},
            headers={"Authorization": "Bearer valid-tok", "tenant_id": "1"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["response"] == "You have 1 company: Acme Corp."
        assert _company_spy.called

    def test_docs_tool_call_end_to_end(self, monkeypatch):
        """Full pipeline: docs query → search_documentation called → answer returned."""
        tc = tool_call("fake_search_documentation", {"query": "what is IMS", "top_k": 5})
        fake_llm = FakeLLM(
            chat_responses=[ChatStructure(query_type=QueryType.product_docs_query)],
            docs_responses=[
                AIMessage(content="", tool_calls=[tc]),
                AIMessage(content="Nobious IMS is an inventory management system."),
            ],
        )
        client = self._make_client(fake_llm, monkeypatch)

        resp = client.post(
            "/api/chat",
            json={"query": "what is IMS?"},
            headers={"Authorization": "Bearer valid-tok", "tenant_id": "1"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["response"] == "Nobious IMS is an inventory management system."
        assert _docs_spy.called

    def test_session_continuity_across_requests(self, monkeypatch):
        """Same session_id passed on second request is echoed back in the response."""
        fake_llm = FakeLLM(
            chat_responses=[
                ChatStructure(query_type=QueryType.account_query),
                ChatStructure(query_type=QueryType.account_query),
            ],
            account_responses=[
                AIMessage(content="First answer."),
                AIMessage(content="Second answer."),
            ],
        )
        client = self._make_client(fake_llm, monkeypatch)
        headers = {"Authorization": "Bearer valid-tok", "tenant_id": "1"}

        r1 = client.post("/api/chat", json={"query": "q1"}, headers=headers)
        assert r1.status_code == 200
        session_id = r1.get_json()["session_id"]
        assert session_id

        r2 = client.post(
            "/api/chat",
            json={"query": "q2", "session_id": session_id},
            headers=headers,
        )
        assert r2.status_code == 200
        assert r2.get_json()["session_id"] == session_id
