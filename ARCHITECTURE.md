# Overtone Architecture

## Framing

Live meeting layer: Recall bot joins Meet/Zoom/Teams, presenter page is bot camera, Gemini Live (or OpenAI Realtime) speaks with answers grounded in an indexed deck. Abstain when thin. No webhook voice path.

## Packages (`backend/app`)

| Package | Responsibility |
|---------|----------------|
| `config` | Settings + provider resolution |
| `db` | SQLAlchemy engine, `v2_*` models |
| `storage` | Local + GCS object layout under `v2/presentations/{id}/` |
| `indexing` | Convert → Vision → quality gate → embed → pgvector |
| `meetings` | Recall client, launch, bot-status webhook |
| `realtime` | WS relay, tools, Gemini/OpenAI adapters |
| `domain` | Agents, customers, session store |
| `http` | Routers only |

## Data

- Tables: `v2_presentations`, `v2_sessions`, `v2_api_keys`, `v2_agents`, `v2_presentation_chunks`
- GCS: `v2/presentations/{id}/source|images|derived/`
- Redis (optional): prefix `v2:`

## HTTP

- `POST /auth/admin`
- `/api/v1/presentations/*`
- `/api/v1/agents/*`
- `/api/v1/sessions/*` (launch, get, leave)
- `/api/v1/customers/*` (admin)
- `/ws/realtime/{session_id}`, `/ws/presentation/{session_id}`
- `/webhooks/recall/bot-status`, `/webhooks/recall/chat`

## Roadmap (not MVP)

Escalate-to-human queue, claim→source audit UI, multi-instance WS fan-out, billing IAM.
