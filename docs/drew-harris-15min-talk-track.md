# Drew Harris — 15-minute talk track + follow-up

**Call goal:** Prove Meet join + live grounded flow; map to escalate-don’t-guess; earn a second technical conversation — not a cold fundraise.

**Show him:** [overtone-architecture-for-partners.md](./overtone-architecture-for-partners.md)

---

## Before you join (2 minutes)

1. Fresh Meet link; launch a **new** bot after the latest backend deploy.  
2. Deck indexed and **ready** (spot-check a middle slide has real text).  
3. Scripted asks:
   - Works: “Explain this slide” / “Go to Market Opportunity” (or whatever title exists).  
   - Honest fail: ask something **not** on the deck → expect abstain / “not in source.”  
4. Have the architecture MD open (or screen-share the mermaid diagrams).  
5. Mindset: **meeting adapter for his roadmap**, not “buy my unfinished product.”

---

## Spoken script (~15 min)

### 0:00–1:30 — Open (frame)

> “Drew — thanks for the time. I’ll keep this tight: how the bot joins the room, how it stays grounded in a deck/session, and where I’d put abstain/escalate — same philosophy you described, not a zero-hallucination guarantee.
>
> Overtone is under active build. I’m showing architecture and a live join path, not a finished compliance product. Where I think it fits you is the Meet/Zoom participant layer on your protégé roadmap.”

### 1:30–3:00 — Architecture snapshot (share MD)

> “High level: Recall joins as a participant and opens a presenter page as the bot camera. Mic audio goes to a realtime speech model — Gemini Live preferred — through our backend relay. Tool calls on the backend — navigate, get slide details, search the indexed deck — return slide text. The voice model is instructed to speak only from those results.
>
> Indexing: Vision extracts per-page text, we embed into pgvector, and we fail the index if Vision returns empty stubs. That’s how we avoid ‘Slide 4’ pretending to be knowledge.”

Point at the **System context** and **Grounding path** diagrams.

### 3:00–8:00 — Live Meet

> “I’ll drop the bot in now.”

Do:

1. Bot joins → short greeting (one time).  
2. “Explain this slide.”  
3. “Go to [Market Opportunity / known section] and explain that.”  
4. Optional: one off-deck question → “That’s not in the source material — I’d escalate rather than guess.”

If something glitches: stay calm.

> “That’s a live edge — here’s what failed and what the architecture does next. Happy to show the recovery path.”

Do **not** apologize for two minutes. Do **not** invent features.

### 8:00–11:30 — Map to his four guardrails

> “On your guardrails — my mapping:
>
> One and two — context sufficiency: vague asks should clarify before answering.  
> Three — source first: deck/session index before anything external.  
> Four — escalate: if we can’t ground it, we should hand to a human expert and treat that answer as ground truth.
>
> Today Overtone is strongest on join + live session + deck grounding. The human-escalate queue as first-class ground truth is the piece I’d align to Apex rather than rebuild. That’s where collaboration is more interesting than competition.”

### 11:30–13:30 — Stack (crisp)

> “Stack in one breath: Recall for join and virtual AV; React presenter as output media; FastAPI relay; Gemini Live or OpenAI Realtime; Vision → embeddings → pgvector; Postgres for sessions; GCS for artifacts. Single sticky API instance for demos so WebSockets don’t split.”

### 13:30–15:00 — Close (ask for next step)

Pick **one** primary ask:

> “Does this join path match what you imagined for a protégé in Meet?”

Then:

> “If it’s useful, I’d propose a short spike: meeting join + grounded answer + an escalate stub that logs ‘needs expert’ the way your loop does. Who on your side would own that conversation?”

Only if he leans in hard:

> “I’m not pitching a finished product for sale today. I’m looking for the right shape — design partner, integration track, or later capital — whichever actually helps Expert Scale ship Meet/Zoom protégés. Curious which of those is even on the table for you.”

---

## Phrases to use / avoid

**Use**

- Traceable / source-bound / abstain / escalate  
- Meeting adapter / join path / live session layer  
- Under development / architecture stage  
- Align to your expert-as-ground-truth model  

**Avoid**

- Zero-hallucination guarantee  
- We’re production-ready for enterprise compliance  
- Please invest / fund me (as the opener)  
- Agency-style “we’ll automate everything”  

---

## If he asks “what do you want?”

Short answer:

> “Near term: a technical collaboration on the Meet join + escalate handoff. Medium term: if that works, we can talk commercial shape — integration, partnership, or investment — once you’ve seen it hold up beyond a demo.”

---

## Follow-up email (send within a few hours)

**Subject:** Overtone join path + escalate fit — notes from today

```
Drew —

Thanks for the 15 minutes and for pushing on grounding vs guarantee language.

Quick recap of what I showed:
- Meet join as participant (Recall) + presenter as bot camera
- Realtime voice relay with tool-grounded answers from an indexed deck
- Design stance: source-bound answers; abstain when thin; escalate to human as the right next layer (aligned with how you described Apex)

Architecture one-pager I’m happy to share or walk again:
[attach or link docs/overtone-architecture-for-partners.md]

Proposed next step (if useful on your side):
A short technical spike — join + grounded response + an “escalate / needs expert” stub that matches your handoff model — then decide if there’s a fit as meeting adapter under Apex.

No pressure either way. If you want that spike scoped, tell me who to loop and your preferred Meet/Zoom constraints.

Best,
Atif
ranaatif1299@gmail.com
```

---

## After the call — score yourself

| Signal | Meaning |
|---|---|
| Asks about escalate handoff / API shape | Warm — send spike outline |
| Asks for recording / architecture doc | Warm — send MD same day |
| “Interesting, I’ll think” only | Neutral — one polite follow-up in 5–7 days |
| Pushes to generic RAG debate | Steer back to **join path** |
| Asks commercial terms immediately | Slow down — define spike success first |

---

## Reminder

This call is won by **clarity + honesty + a working join**, not by claiming Apex’s problem is already solved.
