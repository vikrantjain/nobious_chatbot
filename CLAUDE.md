# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (including dev)
uv sync --extra dev

# Run the Flask chat service
uv run flask --app src/chat_service/app run --host 0.0.0.0 --port 5000

# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_chat_service.py -v

# Run a single test by name
uv run pytest tests/test_chat_service.py::test_chat_success -v

# Run a single E2E test class
uv run pytest tests/test_e2e.py::TestAccountQueryPath -v

# Build the documentation search index
uv run python cli/index_docs.py --repo-url <github-docs-repo-url> --index-path ./doc_index

# Interactive test client (authenticates via IMS, then interactive chat loop)
uv run python test_client/chat_client.py --base-url http://localhost:5000 --ims-url https://tenant1.nobious.io:5443
```

## Architecture

The service is a Flask REST API (`POST /api/chat`) backed by a 5-node LangGraph agent. The agent uses `MemorySaver` (LangGraph's in-memory checkpointer) to maintain conversation history per session; `session_id` is passed as the graph's `thread_id`.

### Request flow

1. **`app.py`** validates the Bearer token against IMS, checks rate limit (3 req/min per user via `SessionStore`), then invokes the graph with `config={"configurable": {"thread_id": session_id}}`.
2. **`chat_llm_call`** (entry node) calls the LLM with `with_structured_output(ChatStructure)` to classify the query into `account_query`, `product_docs_query`, or `none` (clarification needed). Returns a LangGraph `Command` that routes dynamically.
3. **`account_llm_call`** / **`docs_llm_call`** invoke the LLM with the appropriate tool set bound. If tool calls are requested, they route to the tool executor; otherwise they return the final response and go to `END`.
4. **`account_tools`** / **`docs_tools`** execute the tool calls and loop back to their respective LLM node.

```
chat_llm_call ──account_query──► account_llm_call ◄──► account_tools
              ──product_query──► docs_llm_call    ◄──► docs_tools
              ──clarification──► END
```

### Key design decisions

- **`access_token` + `tenant_id` injection**: Both are extracted server-side from the JWT claims in `validate_token()` (`app.py`), stored in `AgentState`, and injected into account tool call args by the `account_tools` node at execution time — the LLM never sees or passes them. The client only sends the Bearer token; `tenant_id` is never read from the request.
- **`SessionStore`** (`session.py`) is only used for rate limiting and generating session UUIDs. Conversation history is fully managed by LangGraph's `MemorySaver`.
- **`account_tools.py`** contains the IMS HTTP calls and LangChain `@tool` wrappers together, exporting `ACCOUNT_TOOLS`. **`doc_tools.py`** does the same for BM25S search, exporting `DOC_TOOLS`. Both lists are passed into `create_agent()` in `app.py`.
- **System prompts** live in `src/chat_service/prompts.py` as three separate constants: `ROUTER_SYSTEM_PROMPT` (for `chat_llm_call`), `ACCOUNT_SYSTEM_PROMPT` (for `account_llm_call`), and `DOCS_SYSTEM_PROMPT` (for `docs_llm_call`). All three share formatting rules via `_SHARED_RULES`.
- **Doc index** is a BM25S index built offline by `cli/index_docs.py`. `doc_tools.py` loads it at startup from `DOC_INDEX_PATH`. If the index is missing, `search_documentation` returns empty results (no error).

### Configuration

All config is in `src/chat_service/config.py` via `pydantic-settings`. Values are read from `.env` (copy from `.env.example`). Required env vars for production: `IMS_BASE_URL` (tool API calls), AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`).

### Conventions

- **Logging**: every module defines `logger = logging.getLogger(__name__)` at the top. Account tool HTTP calls are wrapped in `try/except Exception` — log with `logger.error(...)` then re-raise so the agent's tool executor handles the failure message.
- **`QueryType` enum values** are descriptive strings matching member names (`"account_query"`, `"product_docs_query"`, `"none"`), aligned with the field description the LLM sees.
- **`SessionStore.reset()`** is the public method for clearing all session and rate-limit state in tests; do not access `_sessions` or `_request_times` directly.

### Test suites and mocking patterns

There are two levels of tests, using different mocking strategies:

**Unit / integration tests** (`test_chat_service.py`, `test_account_tools.py`, `test_doc_tools.py`) — mock at the outermost boundary. `conftest.py` provides:
- `mock_validate_token` — patches `src.chat_service.app.validate_token`
- `mock_agent_invoke` — patches `get_agent()` with a `MockAgent` (the entire LangGraph graph is bypassed)
- `app` fixture — composes the above, calls `session_store.reset()` between tests (use this public method, not private attrs)

**E2E tests** (`test_e2e.py`) — use the **real compiled LangGraph graph** with `MemorySaver`. Only the LLM and tool functions are replaced:
- `FakeLLM` — passed to `init_chat_model` patch; `with_structured_output()` returns a `_SeqLLM` that yields `ChatStructure` objects, `bind_tools()` returns a `_SeqLLM` that yields `AIMessage` objects (distinguished by whether `search_documentation` appears in the bound tool names).
- Spy-backed fake tool functions (`fake_get_all_companies`, `fake_search_documentation`) replace the real IMS/BM25S calls, wrapped with `lc_tool` into `FAKE_ACCOUNT_TOOLS` / `FAKE_DOC_TOOLS`.
- `TestFlaskE2EPipeline` builds a real Flask test client with the real agent injected via `monkeypatch.setattr("src.chat_service.app.get_agent", ...)`, so the full Flask → session_store → graph path is exercised.
