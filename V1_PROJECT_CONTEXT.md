# AI Meeting Presenter - Project Context

## Overview

This is an **AI Meeting Presenter** system - a document-driven conversational platform that enables real-time, slide-based presentations in video conferencing meetings (Zoom, Google Meet, Microsoft Teams). The system combines RAG (Retrieval-Augmented Generation) with real-time streaming to deliver intelligent, context-aware responses during live meetings.

## Core Concept

Users upload PDF/PPTX presentations with structured metadata. An AI bot joins video meetings, listens for user queries via wake word detection, retrieves relevant information from the presentation, navigates to the correct slide, and responds conversationally - all in real-time.

---

## Architecture Components

### 1. Metadata Schema (Per-Page)
Each presentation page has structured metadata:
- `page_number`
- `title`
- `section_label`
- `content_type` (tables/diagrams/charts/text)
- `key_topics`
- `entities`
- `searchable_content`
- `questions_answered`

### 2. RAG Pipeline
- **Intent Classification** - Understand query type
- **Query Refinement** - Improve query for retrieval
- **Multi-Stage Retrieval**:
  - Manifest routing
  - Hybrid vector + keyword search (Azure AI Search)
  - Question matching
  - Metadata-weighted ranking
- **Confidence Scoring** - Threshold gating for navigation decisions

### 3. Page Navigation Engine
- Command-based navigation (next/previous/go to)
- Query-driven navigation with confidence gating
- Navigation locking (no random jumps)
- Edge case handling:
  - Ambiguous query → Ask clarifying questions
  - No match → Stay on current slide
  - Repeated query → Don't re-navigate
  - Slide-speech alignment

### 4. Recall.ai Integration
Bot lifecycle management for video conferencing:
- **Bot Creation** - `POST /api/v1/bot/` with `output_media.camera.kind: "webpage"`
- **Output Media** - Streams presenter webpage (slides + audio) into meeting
- **Real-Time Transcription** - WebSocket for wake word detection, stop commands, speaker suppression
- **Bot Controls** - Join, leave, mute, force-remove

### 5. Admin Dashboard
- Upload presentations and metadata
- Trigger indexing pipeline
- Create/edit agents
- Assign presentations to agents
- Launch and monitor bots

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI (async) |
| Search | Azure AI Search (hybrid vector + keyword) |
| Real-time | WebSockets |
| Video Integration | Recall.ai |
| Frontend Deployment | Vercel |
| Backend Deployment | AWS |
| Storage | Persistent (sessions, metadata, indexed data) |

---

## V1 Milestone Scope

### What Needs to Be Built/Refined

1. **Metadata Schema Implementation**
   - Strict per-page metadata
   - Content-type-aware enrichment
   - Azure Search schema update
   - Re-indexing pipeline

2. **RAG Pipeline Rebuild**
   - Intent classification
   - Query refinement
   - Multi-stage retrieval
   - Confidence scoring with threshold gating
   - Deterministic behavior (same query = same slide)

3. **Page Navigation Engine**
   - High-confidence validation before navigation
   - Context-aware decisions
   - All edge cases handled

4. **Conversational Orchestration**
   - Flow: Classify → Answer → Clarify if needed → Retrieve → Navigate → Speak
   - No slide number references in speech
   - Grounded in metadata
   - No premature navigation

### What Already Exists (Needs Refinement)

- Admin dashboard (upload, indexing, agents, bots)
- Agent studio + bot launch flow
- Full API layer
- Persistent storage

---

## Project Milestones

### Milestone 1: APIs + Test Connectivity
- Customer-facing APIs (create bot, schedule bot, get bot status)
- Auth with `x-api-key`
- Session management with persistent storage
- Recall.ai integration (join, leave, mute, force-remove)
- Customer AI endpoint scaffolding (streaming + full response)

### Milestone 2: Bot Orchestration + Navigation + Frontend
- Full tool calling flow with async job handling
- Token-efficient context injection
- Wake word detection, stop command, background speaker suppression
- Complete page navigation engine
- Frontend with loading animations and smooth transitions

### Milestone 3: Testing + Polish + Deployment
- End-to-end testing (Google Meet, Teams, Zoom)
- Edge case validation
- Bug fixes
- Deployment handoff (AWS)

---

## Key Integration Points

### Recall.ai API Endpoints
```
POST /api/v1/bot/                    - Create bot
GET  /api/v1/bot/{id}/               - Get bot status
POST /api/v1/bot/{id}/leave_call/    - Remove bot from call
POST /api/v1/bot/{id}/output_media/  - Start/change webpage stream
DELETE /api/v1/bot/{id}/output_media/ - Stop output media
POST /api/v1/bot/{id}/send_chat_message/ - Send chat message
```

### Real-Time Transcript WebSocket
```
wss://meeting-data.bot.recall.ai/api/v1/transcript
```

---

## Out of Scope (V2)
- Multi-user authentication
- Generic document templating
- Advanced analytics
- Multi-format ingestion standardization
- Template generalization for arbitrary document types

---

## Long-Term Vision

Automate presentation-based customer success workflows in mid-market. Future capabilities:
- Template generalization for any presentation format
- Native handling of PDF, PPTX, DOCX uploads
- User-provided metadata handling
- Multi-format document compatibility

---

## Project Details

- **Timeline**: 7-10 days for V1
- **Client**: Taran Srivastava
- **Engagement**: Fixed contract for V1, then hourly
- **Deployment Target**: Production-ready for real customer use
