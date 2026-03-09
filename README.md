# Nobious IMS Chatbot

An AI-powered chat service for the Nobious Inventory Management System (IMS). Users can ask natural language questions about their inventory data and Nobious product features via a REST API embedded in the web and mobile applications.

## Architecture

```
Client (web/mobile)
    └── POST /api/chat (Bearer token + query)
            └── Flask API
                    ├── IMS Auth (token validation)
                    ├── Rate limiter (3 req/min per user)
                    ├── Session store (in-memory, last 3 messages + summary)
                    └── LangGraph Agent
                            ├── LLM: Claude Haiku 4.5 (AWS Bedrock)
                            ├── Account tools — 8 IMS API tools (real-time inventory data)
                            └── Doc tools — BM25S full-text search (Nobious documentation)
```

## Project Structure

```
nobious_chatbot/
├── pyproject.toml              # uv project + all dependencies
├── .env.example                # Environment variable template
├── src/
│   └── chat_service/
│       ├── app.py              # Flask app, POST /api/chat
│       ├── agent.py            # LangGraph agent (tools, memory, LLM)
│       ├── prompts.py          # System prompts for each LLM node
│       ├── account_tools.py    # 8 IMS API tools (LangChain @tool)
│       ├── doc_tools.py        # BM25S document search tool (LangChain @tool)
│       ├── config.py           # pydantic-settings config
│       └── session.py          # In-memory session store + rate limiter
├── cli/
│   └── index_docs.py           # CLI: clone GitHub repo + build BM25S index
├── tests/
│   ├── conftest.py
│   ├── test_account_tools.py
│   ├── test_doc_tools.py
│   ├── test_chat_service.py
│   └── test_e2e.py
└── test_client/
    └── chat_client.py          # Interactive CLI test client
```

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- AWS account with Bedrock access (Claude Haiku 4.5 enabled in your region)

## Setup

**1. Clone and install dependencies**

```bash
git clone <repo-url>
cd nobious_chatbot
uv sync --extra dev
```

**2. Configure environment**

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Description |
|---|---|
| `IMS_BASE_URL` | Nobious IMS base URL (e.g. `https://tenant1.nobious.io:5443`) |
| `AWS_REGION` | AWS region where Bedrock is enabled (e.g. `us-east-1`) |
| `AWS_ACCESS_KEY_ID` | AWS access key with Bedrock permissions |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `GITHUB_REPO_URL` | GitHub repo URL containing Nobious documentation |
| `GITHUB_TOKEN` | GitHub token (required for private repos) |
| `DOC_INDEX_PATH` | Local path to store the BM25S index (default: `./doc_index`) |
| `MAX_QUERY_LENGTH` | Max characters per query (default: `200`) |
| `RATE_LIMIT_PER_MIN` | Max requests per user per minute (default: `3`) |

**3. Build the documentation index**

```bash
uv run python cli/index_docs.py --repo-url <github-docs-repo-url> --index-path ./doc_index
```

This clones the repo and builds a BM25S full-text search index from all `.md`, `.txt`, and `.rst` files.

## Running the Service

```bash
uv run flask --app src/chat_service/app run --host 0.0.0.0 --port 5000
```

For production, use a WSGI server:

```bash
uv run gunicorn "src.chat_service.app:app" --bind 0.0.0.0:5000
```

## API

### POST /api/chat

Send a chat message.

**Headers**
```
Authorization: Bearer <ims-jwt-token>
Content-Type: application/json
```

**Request body**
```json
{
  "query": "How many items are in stock at location WH-01?",
  "session_id": "optional-existing-session-id"
}
```

**Response (200)**
```json
{
  "response": "There are 142 items currently in stock at WH-01...",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Error responses**

| Status | Meaning |
|---|---|
| `400` | Empty query or query too long |
| `401` | Missing or invalid Bearer token |
| `429` | Rate limit exceeded (3 req/min) |
| `500` | Service temporarily unavailable |

## Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Individual suites
uv run pytest tests/test_account_tools.py -v  # 10 tests — IMS tool functions (httpx mocked)
uv run pytest tests/test_doc_tools.py -v      # 5 tests  — BM25S doc search + CLI indexer
uv run pytest tests/test_chat_service.py -v   # 11 tests — Flask API boundary (agent mocked)
uv run pytest tests/test_e2e.py -v            # 19 tests — real LangGraph graph, LLM mocked
```

## Interactive Test Client

```bash
uv run python test_client/chat_client.py \
  --base-url http://localhost:5000 \
  --ims-url https://tenant1.nobious.io:5443
```

Prompts for email/password, authenticates with IMS, then enters an interactive chat loop. Press `Ctrl+C` to exit.

## Documentation Index CLI

```bash
uv run python cli/index_docs.py --help

# Options:
#   --repo-url TEXT      GitHub repo URL to clone/pull  [required]
#   --index-path TEXT    Path to save the BM25S index  [default: ./doc_index]
#   --token TEXT         GitHub personal access token (for private repos)
```

To update the index after documentation changes:
1. Push updated docs to the GitHub repo
2. Re-run `cli/index_docs.py` (it pulls latest automatically)
3. Restart the service

## Account Tools

8 read-only LangChain tools that proxy IMS REST APIs:

| Tool | IMS Endpoint |
|---|---|
| `get_category_list` | `PUT /api/inventory/ticket/getForTypeList` |
| `get_all_companies` | `GET /api/vista/company/allcompanies` |
| `get_company_locations` | `GET /api/vista/location/getMultipleCompanieslocations/{code}` |
| `get_user_assigned_locations` | `GET /api/ims/user/getUserAssingedLocationByUserId/{id}` |
| `search_materials` | `PUT /api/vista/material/search` |
| `get_item_details` | `PUT /api/vista/material/getItemDetailsByVistaLoc/{cmp}/{item}` |
| `get_allocation_history` | `GET /api/inventory/allocation/allocationHistoryByItem/{userId}/{cmp}/{item}` |
| `get_material_location_inventory` | `PUT /api/inventory/materialLocation/getMaterialLocationListByItemByAssignedLocation/{userId}` |

All tools pass the user's Bearer token to IMS APIs, enforcing existing tenant isolation and permissions.

## Behavior and Constraints

- **Read-only**: The agent never suggests or performs write operations.
- **Domain-scoped**: Only answers questions about Nobious IMS features or the user's own account data. Out-of-domain questions receive: *"I don't have information about the subject"*
- **Session memory**: Retains last 3 message pairs + 1 compacted summary per session. History is discarded on session end.
- **Response format**: Plain text, dates as `MM/DD/YYYY`, currency as `$X,XXX.XX`, lists capped at 5-10 items.
- **Fail fast**: If Bedrock or IMS APIs are unavailable, responds with: *"Chat is temporarily unavailable. Please try again later."*
