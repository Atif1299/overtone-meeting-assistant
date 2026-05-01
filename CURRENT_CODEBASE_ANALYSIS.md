# Codebase Analysis - Overtone AI Meeting Presenter

## Project Overview

Overtone is an **autonomous AI presentation agent** that joins video meetings (Zoom, Google Meet, Microsoft Teams), presents slide decks, and answers questions in real-time using a speech-to-speech pipeline.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           OVERTONE ARCHITECTURE                             │
└────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────────┐     ┌───────────────────┐
│   Meeting    │     │   Overtone       │     │   OpenAI          │
│   Platform   │◄───►│   Backend        │◄───►│   Realtime API    │
│ (Meet/Zoom)  │     │   (FastAPI)      │     │   (Speech-to-     │
└──────┬───────┘     └────────┬─────────┘     │    Speech)        │
       │                      │               └───────────────────┘
       │  Recall.ai Bot       │
       │  joins meeting       │  Tool calls executed server-side:
       │                      │  ┌─────────────────────────────┐
       │                      │  │  search_and_answer (DECK)   │
       │                      │  │  navigate_to_slide          │
       │                      │  │  fetch_external_data ←──────│── YOUR WORK
       │                      │  │  get_slide_details          │
       │                      │  │  leave_call / mute / unmute │
       └──────────────────────┘  └─────────────────────────────┘
```

---

## Directory Structure

```
overtone/
├── backend/                     # Python 3.11, FastAPI
│   ├── api/
│   │   ├── realtime_relay.py    # ★ WebSocket relay to OpenAI Realtime API
│   │   │                        #   Contains _simulate_external_job() STUB
│   │   ├── presentations.py     # Upload/manage presentations
│   │   ├── launch_bot.py        # Bot launch endpoints
│   │   ├── sessions.py          # Session management
│   │   └── webhook_recall.py    # Recall.ai webhooks
│   │
│   ├── orchestrator/
│   │   ├── rag_retriever.py     # ★ DECK-BASED RAG (Azure Search)
│   │   ├── realtime_tools.py    # ★ Tool definitions + executor
│   │   ├── llm_reasoner.py      # LLM reasoning for tool selection
│   │   ├── ws_manager.py        # WebSocket connection manager
│   │   └── tts_client.py        # Text-to-speech client
│   │
│   ├── indexer/
│   │   ├── search_indexer.py    # Azure Search index schema + upload
│   │   ├── pipeline.py          # Full indexing workflow
│   │   ├── metadata_enricher.py # Vision-based metadata extraction
│   │   ├── converter.py         # PDF/PPTX to images
│   │   └── manifest.py          # Presentation manifest builder
│   │
│   ├── services/
│   │   ├── azure_search.py      # Azure AI Search client
│   │   ├── blob_storage.py      # Azure Blob Storage client
│   │   ├── recall_client.py     # Recall.ai API client
│   │   ├── session_store.py     # In-memory session store
│   │   ├── storage.py           # Local file storage
│   │   └── agent_store.py       # Agent prompt templates
│   │
│   ├── models/
│   │   ├── presentation.py      # Presentation data model
│   │   ├── bot_session.py       # Bot session model
│   │   └── metadata.py          # Metadata models
│   │
│   ├── agents/
│   │   └── runtime.py           # Agent system prompt composition
│   │
│   ├── config.py                # Settings from .env
│   ├── database.py              # SQLAlchemy setup
│   └── main.py                  # FastAPI app entry point
│
├── frontend/                    # React + Vite (slide viewer)
│   └── src/
│       ├── hooks/               # useRealtimeAgent, usePresentationTransport
│       └── components/          # SlideViewer, PresentationStage
│
├── dashboard/                   # React + Vite (admin UI)
│   └── src/
│       ├── pages/               # Launch, Agents, Presentations
│       └── components/          # BotConfigForm, AgentEditor
│
├── presentations/               # Local presentation storage
│   └── {uuid}/
│       ├── meta.json            # Presentation metadata
│       ├── index.json           # Page index
│       ├── chunks.json          # Searchable chunks
│       └── provided_metadata.json # Customer-provided metadata
│
└── docs/
    ├── account_brief_68.json    # ★ EXTERNAL DATA SOURCE (your target)
    └── meeting_briefing_68.json # Alternate briefing format
```

---

## Key Files Deep Dive

### 1. realtime_relay.py (YOUR ENTRY POINT)

**Location:** `backend/api/realtime_relay.py`

This is the WebSocket relay between the browser and OpenAI's Realtime API. It intercepts tool calls and executes them server-side.

**Critical Section - Lines 728-802:**

```python
async def _simulate_external_job(self, query: str, call_id: str) -> None:
    """Simulate a long-running external job.
    Wait 30s, then simply 'return' the query as the data.
    """
    # ┌─────────────────────────────────────────────────────────┐
    # │  THIS IS THE STUB YOU NEED TO REPLACE                   │
    # │  Currently: sleep 30s, echo query                       │
    # │  Target: RAG retrieval from account_brief JSON          │
    # └─────────────────────────────────────────────────────────┘
    
    await asyncio.sleep(30)  # <-- REPLACE: Actual RAG retrieval
    search_data = f"Results for: {query}"  # <-- REPLACE: Real results
    
    # Inject results into conversation
    injection_text = (
        f"NOTIFICATION: The external search for '{query}' has completed. "
        "Do NOT share the data yet. First, tell the participant..."
        f"{search_data}"
    )
    
    await self._openai_ws.send(json.dumps({
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": injection_text}],
        },
    }))
    await self._openai_ws.send(json.dumps({"type": "response.create"}))
```

**How it's triggered:**

```python
# Line ~650 in _handle_openai_message()
if tool_name == "fetch_external_data":
    asyncio.create_task(self._simulate_external_job(query, call_id))
```

---

### 2. realtime_tools.py (Tool Definitions)

**Location:** `backend/orchestrator/realtime_tools.py`

**fetch_external_data Tool Definition (Lines 156-175):**

```python
{
    "type": "function",
    "name": "fetch_external_data",
    "description": (
        "Use to fetch data that is NOT on the slides "
        "(e.g., 'tell me about the last 16 months performance'). "
        "This spins up an asynchronous background task because the "
        "3rd party API takes a long time. When you call this tool, "
        "immediately say something like: 'I'm running an external "
        "search on that — give me a moment.'"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The specific query to send to the external data API.",
            }
        },
        "required": ["query"],
    },
}
```

**Other Available Tools:**

| Tool | Purpose |
|------|---------|
| `search_and_answer` | Search deck content, navigate, return slide content |
| `navigate_to_slide` | Direct navigation to specific page number |
| `get_slide_details` | Get rich metadata for a specific page |
| `leave_call` | Make bot leave the meeting |
| `mute_self` / `unmute_self` | Control bot audio |
| `send_chat_message` | Send text to meeting chat |

---

### 3. rag_retriever.py (Deck-Based RAG Pattern)

**Location:** `backend/orchestrator/rag_retriever.py`

This is the existing RAG implementation for deck content. You can follow similar patterns.

**Key Function:**

```python
async def search_presentation(
    query: str,
    presentation_id: str,
    settings: Settings | None = None,
) -> list[dict]:
    """
    Hybrid search: keyword + vector (Azure AI Search)
    
    Flow:
    1. Tokenize query
    2. Generate query embedding (text-embedding-3-large, 3072 dims)
    3. Azure Search hybrid query (keyword + vector)
    4. Re-rank results with title/section boost
    5. Return top 5 hits
    """
    settings = settings or get_settings()
    terms = _tokenize(query)
    azure = AzureSearchClient(settings)
    
    if azure.enabled:
        query_vector = await _generate_query_embedding(query, settings)
        azure_hits = await azure.filtered_search_v2(
            query=query,
            document_id=presentation_id,
            query_vector=query_vector,
            top=5,
        )
        normalized_hits = _rank_hits(azure_hits, terms=terms, query=query)
        return normalized_hits
    
    # Local keyword fallback
    chunk_rows = storage_mod.load_chunk_rows(presentation_id)
    return _rank_hits(chunk_rows, terms=terms, query=query)
```

**Ranking Logic:**

```python
def _rank_hits(rows, *, terms, query) -> list[dict]:
    for row in rows:
        score = azure_score  # Start with Azure's score
        
        # Title boost (+4.0 per matching term)
        for term in terms:
            if term in title.lower():
                score += 4.0
            if term in section.lower():
                score += 2.0
        
        # Exact phrase match bonus
        if query.lower() in content.lower():
            score += 5.0
```

---

### 4. azure_search.py (Search Client)

**Location:** `backend/services/azure_search.py`

**Hybrid Search Method:**

```python
async def filtered_search_v2(
    self,
    *,
    query: str,
    document_id: str,
    query_vector: list[float],
    top: int = 5,
) -> list[dict[str, Any]]:
    """Hybrid search: keyword + vector"""
    
    payload = {
        "search": query or "*",
        "filter": f"document_id eq '{document_id}'",
        "top": top,
        "queryType": "simple",
        "select": "id,document_id,page_number,title,content_text,...",
        "vectorQueries": [
            {
                "kind": "vector",
                "vector": query_vector,
                "k": top * 2,
                "fields": "content_vector,title_vector,questions_vector",
            }
        ],
    }
```

---

### 5. search_indexer.py (Index Schema)

**Location:** `backend/indexer/search_indexer.py`

**Azure Search Index Schema:**

```python
INDEX_SCHEMA = {
    "name": "overtone",
    "fields": [
        # Identifiers
        {"name": "id", "type": "Edm.String", "key": True},
        {"name": "document_id", "type": "Edm.String", "filterable": True},
        {"name": "page_number", "type": "Edm.Int32", "filterable": True},
        
        # Searchable text
        {"name": "title", "type": "Edm.String", "searchable": True},
        {"name": "content_text", "type": "Edm.String", "searchable": True},
        {"name": "searchable_content", "type": "Edm.String", "searchable": True},
        {"name": "questions_answered", "type": "Collection(Edm.String)", "searchable": True},
        
        # Vector fields (3072 dimensions - text-embedding-3-large)
        {"name": "content_vector", "type": "Collection(Edm.Single)", "dimensions": 3072},
        {"name": "title_vector", "type": "Collection(Edm.Single)", "dimensions": 3072},
        {"name": "questions_vector", "type": "Collection(Edm.Single)", "dimensions": 3072},
    ],
    "vectorSearch": {
        "algorithms": [{"name": "overtone-hnsw", "kind": "hnsw", ...}],
        "profiles": [{"name": "overtone-vector-profile", "algorithm": "overtone-hnsw"}],
    },
}
```

---

### 6. config.py (Settings)

**Location:** `backend/config.py`

**Relevant Settings:**

```python
class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_realtime_model: str = "gpt-4o-realtime-preview-2024-12-17"
    
    # Azure Search
    azure_search_endpoint: str = ""
    azure_search_key: str = ""
    azure_search_index_name: str = "overtone"
    
    # Azure Blob Storage
    azure_blob_account_url: str = ""
    azure_blob_account_key: str = ""
    azure_blob_container_name: str = "presentations"
    
    # Redis (for session caching)
    redis_url: str = ""
    redis_key_prefix: str = "voicenav"
    
    # Session
    session_ttl_seconds: int = 86400
```

---

## Data Flow: Tool Execution

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TOOL EXECUTION FLOW                                   │
└─────────────────────────────────────────────────────────────────────────┘

1. User speaks in meeting
   │
   ▼
2. Audio captured by Recall.ai bot → sent to browser
   │
   ▼
3. Browser sends audio via WebSocket to backend relay
   │
   ▼
4. Relay forwards to OpenAI Realtime API
   │
   ▼
5. OpenAI returns response.done with function_call
   │
   ├─── tool_name: "search_and_answer"
   │    └─► RealtimeToolExecutor._search_and_answer()
   │        └─► rag_retriever.search_presentation()
   │            └─► Azure Search (hybrid)
   │
   ├─── tool_name: "fetch_external_data"  ←── YOUR FOCUS
   │    └─► asyncio.create_task(_simulate_external_job())
   │        └─► [STUB: sleep 30s, echo query]
   │        └─► Inject results via conversation.item.create
   │
   └─── tool_name: "navigate_to_slide"
        └─► ws_manager.broadcast_json(navigate event)
   │
   ▼
6. OpenAI generates spoken response using tool result
   │
   ▼
7. Audio streamed back to meeting via bot
```

---

## Session State

**In-Memory Session Store:** `backend/services/session_store.py`

```python
class SessionStore:
    async def register_session(self, session: BotSession):
        self._sessions[session.session_id] = session
    
    async def get_by_session_id(self, session_id: str) -> BotSession | None:
        return self._sessions.get(session_id)
```

**Session Extra Data (for context retention):**

```python
session.extra = {
    "current_page": 1,
    "muted": False,
    "agent_system_prompt": "...",
    "auto_present_pages": 0,
    # You can add:
    "last_retrieval_context": {...},  # For follow-up handling
    "retrieval_cache_ttl": 300,
}
```

---

## Integration Points for account_brief RAG

### Option A: Extend Existing Azure Search

```python
# Create new index: "overtone-account-brief"
# Reuse search_indexer.py patterns
# Add to rag_retriever.py or create account_brief_retriever.py
```

### Option B: Separate In-Memory Search

```python
# Load account_brief JSON at startup
# Use sentence-transformers or OpenAI embeddings
# FAISS or simple cosine similarity
# Faster for single-file use case
```

### Option C: Hybrid Approach

```python
# Tier 1: In-memory pre_answered_qa matching
# Tier 2: Azure Search for deep content search
# Best of both worlds
```

---

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| **CREATE** | `backend/services/account_brief_rag.py` | RAG retrieval for account_brief JSON |
| **CREATE** | `backend/indexer/account_brief_indexer.py` | One-time indexing of account_brief |
| **MODIFY** | `backend/api/realtime_relay.py` | Replace `_simulate_external_job()` |
| **MODIFY** | `backend/config.py` | Add account_brief path config |
| **OPTIONAL** | `backend/services/retrieval_cache.py` | Session-level context caching |

---

## Testing

**Existing Tests:** `backend/tests/`

| Test File | Purpose |
|-----------|---------|
| `test_rag_retriever.py` | RAG retrieval tests |
| `test_search_indexer.py` | Azure Search indexing |
| `test_indexing_and_rag.py` | End-to-end indexing + retrieval |

**Manual Testing:**

```bash
# Run backend
cd backend && uvicorn main:app --reload --port 8000

# API docs
open http://localhost:8000/docs

# Test RAG endpoint (if exposed)
curl -X POST http://localhost:8000/api/test-rag \
  -H "Content-Type: application/json" \
  -d '{"query": "How much did we spend?"}'
```

---

## Environment Variables

```env
# Required for RAG
OPENAI_API_KEY=sk-...
AZURE_SEARCH_ENDPOINT=https://xxx.search.windows.net
AZURE_SEARCH_KEY=...
AZURE_SEARCH_INDEX_NAME=overtone

# Optional for account_brief (you may add)
ACCOUNT_BRIEF_PATH=./docs/account_brief_68.json
ACCOUNT_BRIEF_INDEX_NAME=overtone-account-brief
```
