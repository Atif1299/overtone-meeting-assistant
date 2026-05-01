# AI Meeting Presenter - Project Context

## Overview

**Overtone** is an autonomous AI presentation agent that joins video meetings (Zoom, Google Meet, Microsoft Teams) as a real participant, presents slide decks, and engages in live Q&A with the audience.

---

## Current Engagement (April 2026)

### Client
- **Name**: Taran Srivastava (via Upwork)
- **Team**: Manish Chandra, Abhran

### What Already Exists (Completed by Client Team)
1. Bot lifecycle + Recall.ai integration
2. Output media driving presenter UI + audio stream
3. Real-time transcript WebSocket for wake word + control logic
4. Backend orchestration handling sessions, tool calls, and navigation logic
5. Deck-based RAG (search slides, navigate, answer from deck content)

### Current Scope (What You're Building)
**RAG Pipeline for External Data (account_brief JSON)**

The system needs to handle questions that AREN'T answered by the presentation deck by searching a large JSON file (~15k rows) containing Google Ads account performance data.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER ASKS A QUESTION                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   Is it in the DECK?          │
                    └───────────────────────────────┘
                           │              │
                          YES            NO
                           │              │
                           ▼              ▼
              ┌─────────────────┐  ┌─────────────────────────────┐
              │ search_and_answer│  │ fetch_external_data          │
              │ (existing, works)│  │ (STUB - YOUR WORK)          │
              └─────────────────┘  └─────────────────────────────┘
                           │              │
                           │              ▼
                           │    ┌─────────────────────────────┐
                           │    │ RAG over account_brief.json │
                           │    │ - pre_answered_qa (fast)    │
                           │    │ - talking_points (fast)     │
                           │    │ - deep semantic search      │
                           │    └─────────────────────────────┘
                           │              │
                           ▼              ▼
              ┌─────────────────────────────────────────────────┐
              │           SPOKEN RESPONSE TO USER                │
              └─────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11, FastAPI |
| Speech Pipeline | OpenAI Realtime API (speech-to-speech) |
| Deck RAG | Azure AI Search (hybrid vector + keyword) |
| Embeddings | text-embedding-3-large (3072 dims) |
| Video Integration | Recall.ai |
| Session Storage | Redis / In-memory |
| Frontend | React + Vite |
| Deployment | AWS (backend), Vercel (frontend) |

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/api/realtime_relay.py` | WebSocket relay, contains `_simulate_external_job()` STUB |
| `backend/orchestrator/realtime_tools.py` | Tool definitions including `fetch_external_data` |
| `backend/orchestrator/rag_retriever.py` | Deck-based RAG (reference implementation) |
| `backend/services/azure_search.py` | Azure Search client |
| `docs/account_brief_68.json` | External data source (~15k rows) |

---

## Constraints

| Constraint | Target |
|------------|--------|
| Latency | < 1.5 seconds |
| Concurrent Sessions | 1 (future: 5) |
| Timeline | Before Monday (4 days) |

---

## Deliverables

- [ ] Working RAG retrieval from account_brief JSON
- [ ] Two-tier retrieval (fast path + deep search)
- [ ] Context retention for follow-up questions
- [ ] Integration with `fetch_external_data` tool
- [ ] Latency < 1.5 seconds
- [ ] No critical errors

---

## Documentation Files

| File | Description |
|------|-------------|
| [PROJECT_SCOPE.md](PROJECT_SCOPE.md) | Detailed scope, data structure, retrieval strategy |
| [CODEBASE_ANALYSIS.md](CODEBASE_ANALYSIS.md) | Deep dive into existing codebase |

---

## Communication

- **Discord**: Primary communication channel with Manish and Abhran
- **Updates**: Daily progress updates expected
