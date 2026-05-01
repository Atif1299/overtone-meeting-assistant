# Agent Architecture

This folder defines the agent runtime surface for VoiceNav.

## What is DB-backed vs code-backed

- **DB-backed (editable without deploy):**
  - Named agent prompts + versions, active version selection.
  - Optional default `presentation_id` (knowledge base filter) per version.
  - Backed by SQLite via `backend/services/agent_store.py`.
  - Managed from dashboard **Agents** page.

- **Code-backed (built-in tools and runtime wiring):**
  - Tool schemas + tool handlers: `backend/orchestrator/realtime_tools.py`
  - Realtime session wiring: `backend/api/realtime_relay.py`
  - Final instruction composition: `backend/agents/runtime.py`

## Most common change points

1. Change prompt text live (no deploy):
   - Dashboard -> Agents -> create new version -> activate.
2. Change default knowledge base for an agent:
   - Dashboard -> Agents -> choose Knowledge base while saving a version.

3. Change tool behavior:
   - Edit `backend/orchestrator/realtime_tools.py`.

4. Change how prompt is injected into realtime session:
   - Edit `backend/agents/runtime.py`.
