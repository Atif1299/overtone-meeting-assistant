# Project Scope - Account Brief RAG Pipeline

## Overview

This project involves building a **RAG (Retrieval-Augmented Generation) pipeline** for the `account_brief` JSON dataset. The AI Meeting Presenter already handles deck-based Q&A. Now it needs to fall back to a large structured JSON file (~15k rows) when the answer isn't found in the presentation slides.

---

## Client Requirements

### Core Functionality

When a participant asks a question during a meeting:

1. **1.a** - If answer is found in the deck → Share from the deck (existing functionality)
2. **1.b** - If answer is NOT in the deck → RAG search from `account_brief` JSON and answer

### Additional Conditions

| Requirement | Description |
|-------------|-------------|
| **Context Retention** | Follow-up questions should retain retrieval context. No re-retrieval unless topic changes. |
| **Intelligent Routing** | System must automatically detect if query is deck-related or requires external data |
| **Graceful Handoff** | When falling back to account_brief, say: *"That question does not seem to be a part of the deck, could you please give me a moment while I look deeper into this?"* |

---

## Data Source: account_brief_68.json

### Structure (10 Sections, ~15k lines)

| Section | Line Range | Description | Retrieval Priority |
|---------|------------|-------------|-------------------|
| `meta` | 1-14 | Account metadata, analysis period, agenda | Low |
| `account_context_card` | 16-100 | Health score, at-a-glance metrics, top concerns | Medium |
| `account_summary` | 103-145 | Current vs prior period metrics (spend, ROAS, CPA, conversions) | High |
| `performance_trends` | 146-250 | Monthly trend data, best/worst months | Medium |
| `campaigns` | ~250-2900 | All 34 active + 139 paused campaigns with full metrics | Medium |
| `ad_groups` | ~2900-9450 | Ad group performance data | Low |
| `keywords` | ~9450-11196 | Keyword metrics (7742 with zero conversions) | Low |
| `ads` | ~11196-13000 | Individual ad performance | Low |
| `recent_changes` | ~13000-14978 | Audit log of changes (60 changes in period) | Low |
| `talking_points` | 14979-15002 | **HIGH PRIORITY** - Pre-summarized wins, concerns, next steps | **Critical** |
| `pre_answered_qa` | 15004-15117 | **HIGH PRIORITY** - 28 pre-answered Q&A pairs | **Critical** |

### High-Value Sections for Fast Retrieval

#### talking_points
```json
{
  "wins": ["[Search] Bags at 9.71x ROAS", "4AllPromos Brand at 5.22x ROAS", ...],
  "concerns": ["Only 0.7% IS despite strong 2.79x ROAS", ...],
  "next_steps": ["Pause '4 allpromotion' — $982.26 spend, 0 conversions", ...]
}
```

#### pre_answered_qa (28 Q&A pairs)
```json
[
  {"q": "How much did we spend?", "a": "$2,172,178.94 total spend..."},
  {"q": "What is our ROAS?", "a": "Blended ROAS: 2.81x. Down 0.32x..."},
  {"q": "Which campaign is performing best?", "a": "[Search] Bags leads with 9.71x ROAS..."},
  ...
]
```

---

## Retrieval Strategy

### Two-Tier Approach

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Query                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  TIER 1: Fast Path (< 200ms)                                    │
│  ─────────────────────────────                                  │
│  • Check pre_answered_qa for exact/fuzzy match                  │
│  • Check talking_points for keyword overlap                     │
│  • If confidence > threshold → Return immediately               │
└─────────────────────────────────────────────────────────────────┘
                              │
                    No match / Low confidence
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  TIER 2: Deep Search (< 1.3s remaining)                         │
│  ──────────────────────────────────                             │
│  • Section-tagged semantic search                               │
│  • Query → Embedding → Vector search over structured chunks     │
│  • Metadata filtering (campaign_id, ad_group_id, etc.)          │
│  • De-duplication (same entity appearing in multiple sections)  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Context Cache (Session-Level)                                  │
│  ─────────────────────────────                                  │
│  • Store last retrieval results                                 │
│  • Follow-up detection → Reuse cached context                   │
│  • TTL: Session duration                                        │
└─────────────────────────────────────────────────────────────────┘
```

### Chunking Strategy

| Section Type | Chunking Approach |
|--------------|-------------------|
| `pre_answered_qa` | Each Q&A pair = 1 chunk (embed question for matching) |
| `talking_points` | Each bullet point = 1 chunk with category tag |
| `account_summary` | Single chunk with all metrics |
| `campaigns` | Each campaign = 1 chunk with full metrics |
| `ad_groups` | Each ad_group = 1 chunk (filter by campaign_id) |
| `keywords` | Aggregate by match_type or top-N by spend |
| `recent_changes` | Group by date or resource_type |

### De-duplication

The same `campaign_id` (e.g., `21481254652`) appears in:
- `campaigns.all[]`
- `ad_groups[].campaign_id`
- `keywords[].campaign_id`
- `ads[].campaign_id`

**Solution:** Tag chunks with `section_source` and prioritize:
1. `campaigns` for campaign-level questions
2. `ad_groups` for ad group questions
3. `keywords` for keyword questions

---

## Constraints

| Constraint | Target | Notes |
|------------|--------|-------|
| **Latency** | < 1.5 seconds | End-to-end from query to spoken response |
| **Concurrent Sessions** | 1 (current) | Future: up to 5 |
| **Timeline** | Before Monday | 4 days |

---

## Deliverables

### Milestone 1: Stable, Client-Shareable V1

- [ ] Working RAG retrieval from account_brief JSON
- [ ] Two-tier retrieval (fast path + deep search)
- [ ] Latency < 1.5 seconds
- [ ] Context retention for follow-up questions
- [ ] Integration with existing `fetch_external_data` tool
- [ ] No critical/obvious errors

### Success Criteria

1. Ask "How much did we spend?" → Returns accurate answer from pre_answered_qa
2. Ask "Which campaign needs attention?" → Returns from talking_points.concerns
3. Ask "Tell me about Shopping 3 campaign" → Deep search returns campaign details
4. Follow-up "What's its ROAS?" → Uses cached context, no re-retrieval
5. Response time consistently < 1.5 seconds

---

## Out of Scope (V2)

- Multi-user authentication
- Multiple account_brief files
- Generic document templating
- Advanced analytics dashboard
- Template generalization for arbitrary JSON schemas
