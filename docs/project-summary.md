# Overtone — Project Summary

**Last updated:** April 13, 2026  
**Status:** Working prototype, active iteration

---

## 1. System Overview

Overtone is an AI voice agent that joins video meetings (Google Meet, Zoom, Teams), renders a presentation as its camera feed, and answers audience questions by navigating to relevant slides and speaking answers grounded in the slide content. It uses a direct speech-to-speech pipeline for voice, vision-based extraction for slide indexing, and hybrid vector + keyword retrieval for search.

```
backend/          FastAPI (Python 3.11) — all AI, voice, indexing logic
frontend/         Presentation output-media page (React/Vite, port 5173)
dashboard/        Admin UI — upload decks, launch bots (React/Vite, port 5174)
```

---

## 2. Voice Pipeline: Direct Speech-to-Speech (NOT Transcribe → LLM → TTS)

This is the most important architectural decision to understand. The system uses **OpenAI's Realtime API** — a single WebSocket connection that handles speech input, reasoning, and speech output in one unified pipeline. There is **no separate transcription step, no separate LLM call, no separate TTS call**.

### How audio flows

```
User speaks into meeting
  → Recall.ai bot captures raw audio from the meeting
  → Browser's WavRecorder streams raw PCM16 audio (24kHz) over WebSocket
  → Backend relay (realtime_relay.py) proxies raw audio to OpenAI Realtime API
  → OpenAI processes everything internally:
      1. Voice Activity Detection (detects when user stops speaking)
      2. Speech understanding (operates on audio directly, no exposed transcript)
      3. Reasoning — decides to respond conversationally or call a tool
      4. Speech generation — streams audio tokens back
  → Backend relay forwards audio stream back to browser
  → Browser's WavStreamPlayer plays the audio
  → Recall captures the page's audio output → meeting participants hear it
```

**Audio in, audio out.** OpenAI's model processes speech natively — there is no intermediate text step that we control. This is why latency is significantly lower (~2-4 seconds end-to-end) compared to a traditional ASR → LLM → TTS pipeline.

### What the backend relay does

The relay (`backend/api/realtime_relay.py`) is a **transparent WebSocket proxy** between the browser and OpenAI, with one critical addition: **it intercepts tool calls server-side**. When OpenAI decides to call a tool (search_and_answer or navigate_to_slide), the relay:

1. Catches the function_call event (never forwards it to the browser)
2. Executes the tool server-side (RAG search, slide navigation)
3. Sends the result back to OpenAI as a function_call_output
4. OpenAI generates a spoken response grounded in the tool result

The browser never sees tool calls — it only sees audio streams and navigation commands.

---

## 3. Tool Orchestration

### Registered tools

There are exactly **two tools** registered with the OpenAI Realtime session. OpenAI's model decides autonomously when to call which tool based on what the user said.

| Tool | When OpenAI calls it | What it does |
|------|---------------------|--------------|
| `search_and_answer` | Any content question ("What's your pricing?", "Tell me about the architecture") | Searches the deck via hybrid RAG, navigates to the best slide, returns slide content for OpenAI to speak |
| `navigate_to_slide` | Explicit navigation ("Go to slide 5", "Next slide") or server-driven auto-present | Jumps to a specific page, returns that page's content |

### Tool execution flow

```
OpenAI decides to call a tool (based on user's speech)
  → Sends function_call event over WebSocket to relay
  → Relay intercepts it (strips from browser-bound stream)
  → If search_and_answer: sends filler audio to browser (instant, pre-recorded MP3)
  → Dispatches to RealtimeToolExecutor
  → Tool executes server-side (see details below)
  → Result sent back to OpenAI as function_call_output
  → Relay sends response.create → OpenAI generates spoken response from the tool result
  → Audio streams to browser → meeting participants hear the answer
```

### search_and_answer — step by step

This is the primary RAG tool. When a user asks a content question:

**Step 1 — Manifest check (instant, no API call):**
Looks at the deck's table of contents (section labels, page titles from `manifest.json`). If the question matches a section/title with 2+ significant word overlap (e.g. "pricing" matches the "Pricing" section), routes directly to that page. Handles structural queries like "show me pricing" or "go to case studies" with zero latency.

**Step 2 — Hybrid RAG search (if no manifest match):**
- Generates a 3072-dimension embedding of the search query via OpenAI `text-embedding-3-large`
- Sends to Azure AI Search: simultaneous keyword search + vector search across 3 vector fields (content_vector, title_vector, questions_vector)
- Azure returns results ranked by Reciprocal Rank Fusion (combines keyword and vector relevance)

**Step 3 — Re-ranking:**
Applies additional scoring on top of Azure's results:
- Title match: +4.0 per query term found in slide title
- Section match: +2.0 per query term found in section label
- Keyword frequency scoring on content
- De-duplicated by page (one result per slide)

**Step 4 — Navigation:**
Broadcasts a `navigate` message over the presentation WebSocket → frontend instantly shows the target slide. This happens BEFORE the tool result is returned to OpenAI, so the slide transitions while TTS is still generating.

**Step 5 — Return to OpenAI:**
Sends the slide's full text content (up to 1500 chars) with an instruction: "Speak ONLY from this content. Do not add anything from training knowledge."

### navigate_to_slide — step by step

1. Validates the page number (clamps to 1–total_pages)
2. Broadcasts `navigate` to the frontend via presentation WebSocket
3. Loads the slide content from the local index (`index.json`)
4. Returns content to OpenAI so it knows what to narrate about the slide

### Filler audio layer

When `search_and_answer` is called, there's a 2-4 second delay while embedding + Azure Search + TTS generation runs. To eliminate dead air:

1. Relay immediately sends a pre-recorded filler phrase (e.g. "Let me find that for you") as base64-encoded MP3 over the presentation WebSocket
2. Frontend decodes and plays it instantly (~0ms latency)
3. RAG search runs in parallel
4. When the real answer arrives, OpenAI's speech plays through the normal realtime audio channel
5. 10 filler phrases rotate randomly to avoid repetition; `fillerRef` prevents overlap

### In business terms

> "The system uses OpenAI's speech-to-speech API — audio goes in, audio comes out, with no intermediate text processing on our side. When the AI decides it needs to look something up, it calls one of two tools: a search tool that finds the right slide using hybrid keyword + semantic search, or a navigation tool for direct slide jumps. The backend executes these tools server-side, sends the slide content back, and the AI speaks the answer. A pre-recorded filler phrase plays during the search to eliminate dead air. All tool execution is invisible to the frontend — it only sees audio and slide navigation commands."

---

## 4. Indexing Pipeline

**Entry:** `backend/indexer/pipeline.py` → `run_index_job(presentation_id)`

### Step-by-step:

1. **Upload & Conversion** — `converter.py`  
   - PPTX → PDF via LibreOffice headless, then PDF → PNG pages via `pdftoppm` at 150 DPI.  
   - Output: `presentations/{id}/pages/page_1.png`, `page_2.png`, etc.

2. **Claude Vision Extraction** — `metadata_enricher.py`  
   - Each PNG is sent to `claude-opus-4-6` with a structured extraction prompt.  
   - Concurrency: 3 pages at a time (configurable via `INDEXER_VISION_CONCURRENCY`).  
   - **Fields extracted per page:**

   | Field | Type | Description |
   |-------|------|-------------|
   | `page_number` | int | Slide number |
   | `title` | string | Verbatim slide title (max 10 words) |
   | `section_label` | string | Inferred section: Cover, Pricing, Architecture, etc. |
   | `description` | string | 2-3 sentence summary |
   | `key_topics` | list[string] | Topic keywords |
   | `entities` | list[string] | Company names, products, people, metrics |
   | `content_text` | string | Complete text extraction — all bullets, headings, footnotes |
   | `table_data` | string/null | Markdown table if present |
   | `chart_description` | string/null | Chart type, data points, trends |
   | `diagram_description` | string/null | Components, connections, flow |
   | `content_type` | enum | `title_slide`, `content`, `data`, `diagram`, `comparison`, etc. |
   | `has_table/chart/diagram` | bool | Structural flags |
   | `searchable_content` | string | **Primary RAG field** — dense paragraph with ALL info |
   | `questions_answered` | list[string] | 4-6 questions this slide directly answers |

3. **Embedding & Indexing** — `search_indexer.py`  
   - Embedding model: `text-embedding-3-large` (3072 dimensions).  
   - **Three vectors per page:**
     - `content_vector` — embedding of `searchable_content`
     - `title_vector` — embedding of `"{title} — {section_label}"`
     - `questions_vector` — embedding of joined `questions_answered` list
   - Documents uploaded to Azure AI Search index `overtone` in batches of 100.  
   - Document ID pattern: `{presentation_id}_p{page_num}_c1`

4. **Manifest Generation** — `manifest.py`  
   - Groups consecutive pages sharing the same `section_label` into sections.  
   - Saved as `presentations/{id}/manifest.json`.

---

## 5. Metadata Storage

### Per-presentation files (local mode):

| File | Contents |
|------|----------|
| `meta.json` | filename, status, total_pages, indexed_pages, document_id, azure_indexed_chunks |
| `index.json` | Array of page metadata (all extracted fields above) |
| `chunks.json` | Array of chunks (one per page, formatted for RAG fallback) |
| `manifest.json` | Sections array + pages array with titles and section_labels |
| `pages/page_N.png` | Rendered slide images at 150 DPI |

### Azure AI Search Index Schema (`overtone`):

| Field | Type | Searchable | Notes |
|-------|------|-----------|-------|
| `id` | Edm.String (key) | No | `{pid}_p{n}_c1` |
| `document_id` | Edm.String | No | Filterable, = presentation_id |
| `page_number` | Edm.Int32 | No | Filterable, facetable |
| `title` | Edm.String | Yes | |
| `section_label` | Edm.String | Yes | Filterable, facetable |
| `searchable_content` | Edm.String | Yes | Primary keyword search field |
| `content_text` | Edm.String | Yes | |
| `description` | Edm.String | Yes | |
| `table_data` | Edm.String | Yes | Null if no table |
| `chart_description` | Edm.String | Yes | Null if no chart |
| `diagram_description` | Edm.String | Yes | Null if no diagram |
| `key_topics` | Collection(Edm.String) | Yes | |
| `entities` | Collection(Edm.String) | Yes | |
| `questions_answered` | Collection(Edm.String) | Yes | |
| `content_vector` | Collection(Edm.Single) | Vector | 3072 dims, HNSW cosine |
| `title_vector` | Collection(Edm.Single) | Vector | 3072 dims, HNSW cosine |
| `questions_vector` | Collection(Edm.Single) | Vector | 3072 dims, HNSW cosine |

**Vector config:** HNSW with m=4, efConstruction=400, efSearch=500, cosine metric.  
**Semantic reranker:** Configured but intentionally NOT used at query time (adds ~1.8-2s latency).

---

## 6. Query & Response Flow (When a User Asks a Question)

```
User speaks in meeting
  → Recall captures audio
  → Frontend WavRecorder streams PCM16 to relay WebSocket
  → OpenAI Realtime API (server_vad) detects speech end
  → OpenAI decides to call search_and_answer tool
  → Relay intercepts function_call (server-side, never sent to browser)
  → Filler audio sent via presentation WS (plays immediately)
  → RealtimeToolExecutor._search_and_answer() executes:
      1. Manifest-first routing (word overlap on section/title labels)
      2. Query embedding via text-embedding-3-large
      3. Azure hybrid search (keyword + 3 vector fields, RRF scoring)
      4. _rank_hits: Azure score + keyword frequency + title boost (+4.0) + section boost (+2.0)
      5. Navigate broadcast via presentation WS (slide changes instantly)
      6. Return slide_content (up to 1500 chars) to OpenAI
  → OpenAI generates TTS from slide_content
  → Audio streams to frontend → Recall captures → meeting hears answer
```

### Scoring Details (`rag_retriever.py → _rank_hits`):

- Azure hybrid RRF score (from vector + keyword fusion)
- Keyword frequency: child matches `min(n,6) * 1.5`, parent matches `min(n,4) * 0.8`
- Exact query string match: `+5.0`
- **Title boost:** each query term found in `title` → `+4.0`
- **Section boost:** each query term found in `section_label` → `+2.0`
- De-duplicated by page (one result per slide)
- Top 5 returned, top 1 used for navigation

### Manifest-First Routing (`realtime_tools.py → _resolve_from_manifest`):

Before hitting Azure Search, checks if the question matches a section label or page title with 2+ significant word overlap. If yes, that page is promoted to the top of results. This handles structural queries like "show me pricing" or "go to case studies" instantly without any API call.

---

## 7. WebSocket Architecture (Two WebSockets per Session)

### WS 1: Presentation Transport — `/ws/presentation/{session_id}`
- **Purpose:** Navigate commands, filler audio, status updates
- **Direction:** Backend → Frontend (primarily)
- **Messages:** `navigate`, `play_filler`, `answer`, `status`, `error`
- **Manager:** `ws_manager.py` — in-memory room dict, broadcasts to all connected clients
- **Reconnect:** Exponential backoff 1s → 16s

### WS 2: Realtime Audio — `/ws/realtime/{session_id}`
- **Purpose:** Voice audio streaming, OpenAI Realtime protocol
- **Direction:** Bidirectional (browser ↔ relay ↔ OpenAI)
- **Relay:** `realtime_relay.py` — proxies between browser and OpenAI, intercepts tool calls server-side
- **Audio format:** PCM16, 24kHz
- **Key behavior:** All function_call events are stripped before forwarding to browser — tool execution is 100% server-side

### Navigation Flow:
```
Tool executor → ws_manager.broadcast_json(session_id, {type: "navigate", target_page: N})
  → Frontend usePresentationTransport → onNavigate(N)
  → useSlideNavigation.goTo(N) → setCurrentPage(N)
  → SlideViewer renders <img src="/api/presentations/{id}/page/{N}/image">
```

---

## 8. Filler Audio (Dead Air Elimination)

**Problem:** 2-4 seconds of silence between user question and AI response (embedding + search + TTS generation).

**Solution:** 10 pre-recorded MP3 filler phrases ("Let me find that for you", "One moment please", etc.) generated with OpenAI TTS (`tts-1`, voice `coral`), stored in `backend/static/fillers/`.

**Flow:**
1. Tool call arrives → `get_random_filler_b64()` returns a random clip as base64
2. Sent via presentation WS: `{"type": "play_filler", "audio_b64": "..."}`
3. Frontend decodes base64 → creates `Audio` object → plays instantly
4. `fillerRef` tracks active filler — stops previous before playing new (prevents overlap)
5. Recall captures page audio → meeting participants hear it immediately

**Timing:** Filler is sent at the exact moment the tool call starts (~0ms). RAG executes in parallel.

---

## 9. Auto-Present Mode (Guided Narration)

**Config:** `auto_present_pages` field in dashboard launch form (0-200, default 0).

**Behavior:**
- **Slide 1:** Content injected at session start. Model opens with a 20-30 word pitch, then narrates.
- **Advancement:** Server-driven, triggered by `input_audio_buffer.speech_started` (user speaks).
- **Gate:** `_model_has_narrated` flag prevents advance before the model finishes its first narration.
- **Per advance:** Server navigates frontend, loads slide content from `index.json`, injects into conversation.
- **After slide N:** Model transitions to Q&A mode.
- **Interruptions:** If user asks a content question, `search_and_answer` handles it normally.

**System prompt tells the model:** "Do NOT call navigate_to_slide yourself. Navigation is automatic. Just narrate and stop."

---

## 10. Known Issues & Limitations

### Navigation Accuracy (PRIMARY ISSUE)
- **Wrong slide selection:** The RAG retriever sometimes returns a semantically similar but incorrect slide. Example: a slide mentioning "pricing" in a bullet competes with the dedicated Pricing slide.
- **Query-content mismatch:** The model sometimes generates poor search queries (e.g., "slide 47 content" instead of the actual topic), leading to wrong results.
- **Speech-navigation desync:** Navigation fires before TTS starts, so the slide changes before the model begins speaking. Usually acceptable but occasionally the model speaks about the previous slide's content while the new slide is showing.

### Grounding
- The GROUNDING LAW in the system prompt works most of the time, but the model occasionally supplements with training knowledge when `slide_content` is sparse or ambiguous.
- The model sometimes says "on slide 25" or references slide numbers despite explicit instructions not to.

### Latency
- **End-to-end:** ~2-5 seconds (VAD 500ms + embedding ~350ms + Azure Search ~150-500ms + TTS ~400-700ms)
- **Azure Search spikes:** Occasionally takes 2-4 seconds (cold index or complex queries)
- **Filler audio bridges the gap** but doesn't reduce actual latency

### Auto-Present
- The advance-on-speech trigger means ANY user sound (cough, background noise) can advance the slide if VAD picks it up.
- No way to go back to a previous slide during auto-present.

### Infrastructure
- Sessions are in-memory — lost on backend restart. Must re-launch bot after any restart.
- `ws_manager` rooms are in-memory — if no frontend is connected, navigate messages are silently dropped.
- Cloudflare tunnel URLs rotate on every restart — .env must be re-patched.

---

## 11. Next Steps

### Structured Per-Page Metadata (Pending Client Decision)
The client is deciding on a specific metadata format for every page type. Once defined, this will require:
1. Reworking `SLIDE_EXTRACTION_PROMPT` in `metadata_enricher.py` to extract the new schema
2. Updating the Azure Search index schema in `search_indexer.py` (requires re-indexing)
3. Updating `_rank_hits` scoring to weight the new metadata fields
4. Potentially adding page-type-specific retrieval strategies (e.g., table queries route differently than diagram queries)

### Improving Navigation Accuracy
- **Q&A pair matching** (Layer 3, partially implemented): `questions_answered` field is in the extraction prompt and index schema. Needs validation with real queries to tune effectiveness.
- **Page-level confidence threshold:** Currently any match (even score 0.4) triggers navigation. Adding a minimum score threshold would prevent weak matches from navigating.
- **Re-ranking with page context:** After initial retrieval, a lightweight re-ranker could consider the conversation context (what slide we're currently on, what was just discussed) to break ties.

### Other Improvements
- **Persistent sessions:** Move from in-memory to Redis/DynamoDB session store for crash recovery.
- **Streaming tool results:** Start TTS generation before the full RAG result is ready (progressive answer).
- **Multi-deck support:** Allow switching between presentations within a single session.
- **Analytics:** Log every query → retrieved page → spoken answer for accuracy measurement and tuning.

---

## 12. Key Files Reference

| File | Role |
|------|------|
| `backend/indexer/pipeline.py` | Top-level indexing orchestrator |
| `backend/indexer/converter.py` | PPTX/PDF → PNG conversion |
| `backend/indexer/metadata_enricher.py` | Claude Vision extraction prompt + dispatch |
| `backend/indexer/search_indexer.py` | Azure Search index schema, embedding, upload |
| `backend/indexer/manifest.py` | Manifest build/save/load |
| `backend/services/storage.py` | All local/cloud persistence |
| `backend/services/azure_search.py` | `AzureSearchClient`, hybrid search |
| `backend/services/filler_audio.py` | Filler audio loader |
| `backend/orchestrator/rag_retriever.py` | Query embedding, hybrid+local ranking |
| `backend/orchestrator/realtime_tools.py` | Tool definitions, search_and_answer, manifest routing |
| `backend/orchestrator/ws_manager.py` | WebSocket room manager |
| `backend/api/realtime_relay.py` | WebSocket relay, event pump, filler, auto-present |
| `backend/agents/runtime.py` | System prompt assembly |
| `backend/api/launch_bot.py` | Bot launch, session creation |
| `backend/config.py` | All env var settings (Pydantic) |
| `frontend/src/App.jsx` | Root component, WS hooks, filler playback |
| `frontend/src/hooks/useRealtimeAgent.js` | OpenAI RealtimeClient lifecycle |
| `frontend/src/hooks/usePresentationTransport.js` | Presentation WS message dispatch |
| `frontend/src/hooks/useWebSocket.js` | Raw WS with reconnect |
| `frontend/src/components/SlideViewer.jsx` | Slide image rendering |
| `dashboard/src/components/BotConfigForm.jsx` | Launch form (agent, presentation, auto-present) |

---

## 13. Agent System

Agents are versioned prompt profiles stored in SQLite (`./data/agents.db` via `services/agent_store.py`).

**Schema:** Each agent version is a row with `agent_name`, `version_number`, `system_prompt`, `presentation_id` (optional default deck), and `is_active` flag.

**Key behaviors:**
- Only one version per agent can be active at a time (`is_active=1`)
- Each version can bind to a default presentation (used if not overridden at launch)
- A `default` agent is auto-created on first run with a generic system prompt
- The dashboard's Agent Studio UI creates/edits versions and activates them

**At launch time:** The active agent version's `system_prompt` is captured into `session.extra["agent_system_prompt"]` — so the prompt is frozen at launch, not affected by subsequent edits.

---

## 14. Session Lifecycle

Sessions track active bot instances. Managed by `services/session_store.py`.

**Storage:** Dual-layer — in-memory dict (`_by_session`) for fast access + optional Redis for persistence across restarts.

**Creation:** `store.create_session()` called from `launch_bot.py` after Recall API confirms bot creation. Stores: `session_id`, `presentation_id`, `bot_name`, `meeting_url`, `agent_mode`, `agent_name`, `agent_version`, `bot_id`, plus an `extra` dict with runtime state.

**Extra dict contents:**
| Key | Purpose |
|-----|---------|
| `relay_status` | `idle` → `connecting` → `connected` → `disconnected` |
| `agent_system_prompt` | Frozen system prompt from agent version |
| `auto_present_pages` | Auto-present slide limit (0 = Q&A only) |
| `relay_profile` | `voicenav` (normal) or `demo` (passthrough) |
| `realtime_errors` | Error counter |
| `tool_calls` / `tool_failures` | Tool execution counters |
| `first_audio_latency_ms` | Time to first audio after connection |

**Expiration:** Sessions auto-expire after `SESSION_TTL_SECONDS` (default 24h). The cleanup loop runs every 60 seconds and evicts expired entries.

**Redis durability:** If `REDIS_URL` is configured, sessions are persisted to Redis with TTL. On restart, `load_from_redis()` rehydrates all sessions. Without Redis, all sessions are lost on restart.

**Bot-to-session mapping:** `_bot_to_session` dict enables fast lookup by Recall bot ID (used by webhook handlers).

---

## 15. Bot Launch Flow

Full sequence from dashboard click to bot in meeting:

```
Dashboard: user fills form (agent, bot name, meeting URL, presentation, mode, auto_present_pages)
  → POST /api/launch-bot
  → Resolve agent: find active version by agent_name
  → Resolve presentation: user selection > agent default > error
  → Resolve mode: user selection > env default (realtime)
  → Check presentation is indexed (status=ready); auto-index if not
  → Generate session_id (UUID)
  → Build output_media_url: {frontend_tunnel}/?session={id}&presentation={id}&mode=realtime&wss={relay_url}
  → Call Recall.ai Create Bot API:
      - meeting_url
      - bot_name
      - output_media.kind = "webpage", url = output_media_url
      - transcript webhook URL (for webhook fallback mode)
  → Recall returns bot_id
  → Create session in store with all metadata
  → Return session_id, bot_id, output_media_url, relay_url to dashboard

Recall bot joins meeting (10-20 seconds):
  → Renders output_media_url as its camera feed
  → Frontend page loads at that URL
  → Frontend connects both WebSockets:
      1. /ws/presentation/{session_id} — for navigation commands
      2. /ws/realtime/{session_id} — for audio relay to speech model
  → Relay connects to speech model's WebSocket
  → Sends session.update with system prompt, tools, VAD config
  → Bot is live — listening for speech
```

---

## 16. Upload & Indexing Flow

Three upload paths are supported:

| Path | Endpoint | Use case |
|------|----------|----------|
| **Direct upload** | `POST /api/upload` | Small files, simple form upload |
| **Chunked upload** | `POST /api/upload/init` → `POST /api/upload/{id}/chunk` → `POST /api/upload/{id}/complete` | Large files, resumable |
| **SAS URL upload** | `POST /api/upload/direct/init` → client uploads to Azure Blob → `POST /api/upload/direct/complete` | Direct-to-cloud, bypasses backend |

All paths enforce `MAX_UPLOAD_BYTES` (default 50MB). After upload completes, `run_index_job()` is dispatched (inline by default, or queued to SQS if `INDEXER_DISPATCH_MODE=queue`).

---

## 17. System Prompt Composition

`compose_realtime_instructions()` in `agents/runtime.py` builds the final prompt sent to the speech model. Structure:

```
[1. Agent's custom system prompt — from agent_store, frozen at launch]

[2. Presentation context — "Active presentation id: '{id}'"]

[3. Deck structure — from manifest.json]
    DECK STRUCTURE (57 slides):
      Slide 1: Cover
      Slides 2-5: Problem Statement
      Slides 6-12: Solution Overview
      ...

[4. Presentation mode — depends on auto_present_pages]
    If > 0: GUIDED PRESENTATION MODE
      - Opening pitch instruction (20-30 words)
      - Phase 1: narrate slides, wait for user speech to advance
      - Phase 2: Q&A after slide N
      - "Do NOT call navigate_to_slide yourself"
    If = 0: Q&A MODE
      - Wait for questions
      - Use search_and_answer

[5. GROUNDING LAW — non-negotiable]
    "Your spoken response MUST be derived EXCLUSIVELY from
     the slide_content field. You are FORBIDDEN from adding
     any information from your training data..."

[6. TOOL RULES]
    1. Advance slides → navigate_to_slide
    2. Content questions → search_and_answer
    3. After answering in Phase 1 → resume presenting
    4. Greetings/small talk → brief response

[7. ANSWER STYLE]
    - 2-3 sentences per slide
    - NEVER mention slide numbers
    - NEVER fabricate
    - Speak as a confident presenter
```

**Backend ownership:** The relay intercepts and drops any `session.update` messages from the browser, preventing the frontend from overriding tools or instructions.

---

## 18. Frontend Rendering

The presentation frontend (`frontend/`) is a React/Vite app loaded by the meeting bot as its camera output.

**SlideViewer:** Renders `<img src="/api/presentations/{id}/page/{N}/image">`. On image error, shows a blank dark div. The `key={page}` prop forces React to unmount/remount on navigation for clean transitions.

**PresentationStage:** Wraps SlideViewer with a header bar (slide number + status indicator) and a hidden `<audio>` element for answer playback.

**Transitions:** A 280ms CSS transition is triggered on every page change via a `transitioning` state flag.

**Image endpoint:** `GET /api/presentations/{id}/page/{N}/image` resolves in order: Azure Blob → local file (`pages/page_N.png`) → SVG fallback with extracted text.

**Audio playback:**
- Filler audio: decoded from base64 in WS message, played via `new Audio()` with overlap prevention (`fillerRef`)
- Speech model audio: played via `WavStreamPlayer` from the `@openai/realtime-api-beta` library through the realtime WebSocket
- Both audio paths go through the browser's Web Audio context, which the meeting bot captures as its audio output

---

## 19. Configuration Reference

All settings are in `backend/config.py` (Pydantic `BaseSettings`, reads from `backend/.env`):

| Setting | Default | Description |
|---------|---------|-------------|
| `VOICE_AGENT_MODE` | `realtime` | `realtime` or `webhook` |
| `STORAGE_BACKEND` | `local` | `local` or `dynamodb` |
| `OPENAI_REALTIME_MODEL` | `gpt-4o-realtime-preview-2024-12-17` | Speech model |
| `OPENAI_REALTIME_VOICE` | `alloy` | Voice: alloy, coral, echo, shimmer |
| `OPENAI_REALTIME_VAD_THRESHOLD` | `0.82` | VAD sensitivity (0.0-1.0) |
| `OPENAI_REALTIME_VAD_SILENCE_MS` | `900` | Silence before end-of-speech |
| `OPENAI_REALTIME_VAD_PREFIX_PADDING_MS` | `450` | Audio kept before speech start |
| `OPENAI_REALTIME_INTERRUPT_RESPONSE` | `false` | Whether user speech interrupts agent |
| `INDEXER_VISION_CONCURRENCY` | `3` | Parallel vision extraction calls |
| `SESSION_TTL_SECONDS` | `86400` | Session expiration (24h) |
| `MAX_UPLOAD_BYTES` | `52428800` | Upload size limit (50MB) |
| `AZURE_SEARCH_INDEX_NAME` | `overtone` | Search index name |

---

## 20. External Services

| Service | Purpose | Key Config |
|---------|---------|------------|
| Recall.ai | Bot joins meetings, captures audio | `RECALL_API_KEY` |
| OpenAI Realtime API | Voice agent (VAD + TTS) | `OPENAI_API_KEY` |
| OpenAI Embeddings | Query + content embeddings | `text-embedding-3-large`, 3072 dims |
| OpenAI TTS | Filler audio generation (one-time) | `tts-1` |
| Anthropic Claude | Vision extraction during indexing | `ANTHROPIC_API_KEY` |
| Azure AI Search | RAG chunk storage + hybrid retrieval | `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_KEY` |
| Azure Blob Storage | Presentation files + slide images | `AZURE_BLOB_ACCOUNT_URL`, `AZURE_BLOB_ACCOUNT_KEY` |
