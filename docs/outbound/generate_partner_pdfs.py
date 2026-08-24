#!/usr/bin/env python3
"""Generate enterprise partner PDFs for Drew Harris follow-up."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_DIR = Path(__file__).resolve().parent

# Enterprise palette — slate / ink (avoid purple/glow AI defaults)
INK = colors.HexColor("#0F172A")
SLATE = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#E2E8F0")
BAND = colors.HexColor("#0B1F33")
ACCENT = colors.HexColor("#0E7490")  # teal, restrained
LIGHT = colors.HexColor("#F8FAFC")
WHITE = colors.white
OK_BG = colors.HexColor("#F1F5F9")


def styles():
    base = getSampleStyleSheet()
    s = {}
    s["cover_brand"] = ParagraphStyle(
        "cover_brand",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=28,
        textColor=WHITE,
        alignment=TA_LEFT,
        spaceAfter=6,
        tracking=1,
    )
    s["cover_sub"] = ParagraphStyle(
        "cover_sub",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=11,
        textColor=colors.HexColor("#94A3B8"),
        leading=16,
        spaceAfter=4,
    )
    s["cover_title"] = ParagraphStyle(
        "cover_title",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=WHITE,
        leading=26,
        spaceBefore=28,
        spaceAfter=10,
    )
    s["cover_meta"] = ParagraphStyle(
        "cover_meta",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        textColor=colors.HexColor("#CBD5E1"),
        leading=14,
    )
    s["h1"] = ParagraphStyle(
        "h1",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=INK,
        spaceBefore=16,
        spaceAfter=8,
        leading=18,
    )
    s["h2"] = ParagraphStyle(
        "h2",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=ACCENT,
        spaceBefore=12,
        spaceAfter=6,
        leading=14,
    )
    s["body"] = ParagraphStyle(
        "body",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        textColor=SLATE,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    )
    s["body_left"] = ParagraphStyle(
        "body_left",
        parent=s["body"],
        alignment=TA_LEFT,
    )
    s["quote"] = ParagraphStyle(
        "quote",
        parent=base["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=10,
        textColor=INK,
        leading=15,
        leftIndent=12,
        rightIndent=12,
        spaceBefore=6,
        spaceAfter=10,
        borderPadding=8,
    )
    s["bullet"] = ParagraphStyle(
        "bullet",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        textColor=SLATE,
        leading=13.5,
        leftIndent=4,
    )
    s["cell"] = ParagraphStyle(
        "cell",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        textColor=SLATE,
        leading=12,
    )
    s["cell_h"] = ParagraphStyle(
        "cell_h",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=WHITE,
        leading=12,
    )
    s["footer"] = ParagraphStyle(
        "footer",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=MUTED,
        alignment=TA_CENTER,
    )
    s["small"] = ParagraphStyle(
        "small",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        textColor=MUTED,
        leading=12,
        spaceAfter=6,
    )
    s["label"] = ParagraphStyle(
        "label",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=ACCENT,
        spaceBefore=2,
        spaceAfter=4,
    )
    return s


def header_footer(canvas, doc, doc_title: str):
    canvas.saveState()
    page_w, page_h = LETTER
    # top rule
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(0.75 * inch, page_h - 0.55 * inch, page_w - 0.75 * inch, page_h - 0.55 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.75 * inch, page_h - 0.45 * inch, "OVERTONE")
    canvas.drawRightString(page_w - 0.75 * inch, page_h - 0.45 * inch, doc_title)
    # bottom
    canvas.line(0.75 * inch, 0.55 * inch, page_w - 0.75 * inch, 0.55 * inch)
    canvas.drawString(0.75 * inch, 0.38 * inch, "Confidential — intended recipient only")
    canvas.drawRightString(page_w - 0.75 * inch, 0.38 * inch, f"Page {doc.page}")
    canvas.restoreState()


def cover_block(story, s, brand_line: str, title: str, meta_lines: list[str]):
    """Full-bleed-style cover using a dark table band."""
    inner = [
        Paragraph("OVERTONE", s["cover_brand"]),
        Paragraph(brand_line, s["cover_sub"]),
        Spacer(1, 8),
        HRFlowable(width="100%", thickness=1, color=ACCENT, spaceBefore=4, spaceAfter=4),
        Paragraph(title, s["cover_title"]),
    ]
    for line in meta_lines:
        inner.append(Paragraph(line, s["cover_meta"]))
    data = [[inner]]
    t = Table(data, colWidths=[6.5 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BAND),
                ("LEFTPADDING", (0, 0), (-1, -1), 28),
                ("RIGHTPADDING", (0, 0), (-1, -1), 28),
                ("TOPPADDING", (0, 0), (-1, -1), 36),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 36),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 18))


def table(headers, rows, col_widths):
    s = styles()
    head = [Paragraph(h, s["cell_h"]) for h in headers]
    body = [[Paragraph(str(c), s["cell"]) for c in row] for row in rows]
    data = [head] + body
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), BAND),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), OK_BG))
    t.setStyle(TableStyle(style_cmds))
    return t


def callout(text: str):
    s = styles()
    inner = Paragraph(text, s["quote"])
    t = Table([[inner]], colWidths=[6.5 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), OK_BG),
                ("BOX", (0, 0), (-1, -1), 1.2, ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return t


def bullets(items: list[str]):
    s = styles()
    return ListFlowable(
        [ListItem(Paragraph(i, s["bullet"]), leftIndent=12, bulletColor=ACCENT) for i in items],
        bulletType="bullet",
        start="•",
        leftIndent=18,
        spaceBefore=2,
        spaceAfter=8,
    )


def build_cover_letter():
    s = styles()
    path = OUT_DIR / "01_Overtone_Follow_Up_Letter.pdf"
    doc = SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
    )
    story = []
    cover_block(
        story,
        s,
        "Live meeting intelligence · Partner correspondence",
        "Follow-Up — Collaboration Discussion",
        [
            "Prepared for: Drew Harris, Founder — Expert Scale (Apex Replicant™)",
            "Prepared by: Muhammad Atif — Overtone",
            "Date: 21 August 2026",
            "Classification: Confidential",
        ],
    )
    story.append(Paragraph("Dear Drew,", s["body_left"]))
    story.append(
        Paragraph(
            "Thank you for the time today and for walking through how Protégé decides when to escalate. "
            "Your framing — refuse when out of specialty, dig deeper when on-scope but thin, then hand off "
            "to the human expert — is the standard we want the live meeting layer to respect.",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "You noted that Protégé today operates through a web interface, and that live meeting join "
            "is the missing piece. That is precisely the path Overtone has been building: a participant "
            "bot in Meet / Zoom / Teams, grounded answers from indexed session sources, and a clear stop "
            "when the source cannot support a reply.",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "As discussed, we are treating next steps as a <b>collaboration partnership</b> — integrate "
            "and prove fit — not a commercial close or capital conversation at this stage.",
            s["body"],
        )
    )
    story.append(Paragraph("Enclosed", s["h2"]))
    story.append(
        bullets(
            [
                "<b>Document 02</b> — Collaboration Spike Outline (scope, success criteria, next steps)",
                "<b>Document 03</b> — Architecture Overview (join path, grounding, stack)",
            ]
        )
    )
    story.append(Paragraph("Requested of you", s["h2"]))
    story.append(
        bullets(
            [
                "Review the spike outline at your convenience",
                "Optionally try Launch on the dashboard with your own Google Meet link",
                "If useful, schedule a short working session to align escalate-stub fields with your handoff model",
            ]
        )
    )
    story.append(
        Paragraph(
            "Dashboard (Launch): <b>https://overtone-dashboard-4idrhaffca-uc.a.run.app</b><br/>"
            "Please note: realtime latency is still being optimized (~3–4 seconds in places). "
            "Honest feedback after a self-test is welcome.",
            s["body_left"],
        )
    )
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "I look forward to your thoughts.<br/><br/>"
            "Respectfully,<br/><br/>"
            "<b>Muhammad Atif</b><br/>"
            "Overtone<br/>"
            "ranaatif1299@gmail.com",
            s["body_left"],
        )
    )
    doc.build(story)
    return path


def build_spike():
    s = styles()
    path = OUT_DIR / "02_Overtone_Collaboration_Spike_Outline.pdf"
    title = "Collaboration Spike Outline"

    def on_page(canvas, doc):
        if doc.page > 1:
            header_footer(canvas, doc, title)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    story = []
    cover_block(
        story,
        s,
        "Expert Scale × Overtone — technical collaboration proposal",
        "Collaboration Spike Outline",
        [
            "To: Drew Harris — Expert Scale / Apex Replicant™",
            "From: Muhammad Atif — Overtone",
            "Date: August 2026",
            "Status: Proposal only — no commercial commitment",
        ],
    )

    story.append(Paragraph("1. Purpose", s["h1"]))
    story.append(
        Paragraph(
            "On our discussion you confirmed that Protégé runs primarily through a web interface today, "
            "and that <b>live meeting join</b> is the missing capability. Overtone already joins Meet / Zoom / Teams "
            "as a participant and answers from an indexed deck or session source.",
            s["body"],
        )
    )
    story.append(Paragraph("Escalation model (as you described)", s["h2"]))
    story.append(
        bullets(
            [
                "<b>Out of specialty</b> → refuse / out of scope",
                "<b>On-scope but thin</b> → dig knowledge base deeper → escalate if still insufficient",
                "<b>Lead-gen / limited capacity</b> → escalate serious asks and time commitments to the human expert",
            ]
        )
    )
    story.append(
        Paragraph(
            "This spike wires <b>(A) your judgment ladder</b> into <b>(B) our live join path</b> once, end-to-end.",
            s["body"],
        )
    )

    story.append(Paragraph("2. Goal (2–3 weeks, light)", s["h1"]))
    story.append(
        callout(
            "Bot joins a live meeting → answers only when grounded in session sources → "
            "otherwise abstains or flags <b>needs expert</b> the way your escalate loop does."
        )
    )
    story.append(
        Paragraph(
            "This is a <b>collaboration proof</b>, not a product sale and not an investment discussion. "
            "Commercial shape is deferred until after one clean end-to-end run.",
            s["body"],
        )
    )

    story.append(Paragraph("3. Scope", s["h1"]))
    story.append(Paragraph("In scope", s["h2"]))
    story.append(
        table(
            ["#", "Deliverable"],
            [
                ["1", "Meet join (Recall) + realtime voice + deck/session grounding (existing Overtone path)"],
                [
                    "2",
                    "Escalation mapping stub: out-of-scope refuse / on-scope dig / escalate-if-thin → log needs expert",
                ],
                [
                    "3",
                    "Short write-up: what worked, latency notes, what would plug into Apex / Protégé APIs",
                ],
            ],
            [0.4 * inch, 6.1 * inch],
        )
    )
    story.append(Spacer(1, 10))
    story.append(Paragraph("Out of scope for this spike", s["h2"]))
    story.append(
        bullets(
            [
                "Full Apex / Protégé product integration or production SLA",
                "Pricing, equity, exclusivity, or fundraising",
                "Rebuilding your judgment layer from scratch",
            ]
        )
    )

    story.append(Paragraph("4. Success criteria", s["h1"]))
    story.append(
        bullets(
            [
                "In a live Meet, a <b>grounded</b> question receives a source-bound answer (deck / session).",
                "An <b>out-of-scope</b> or <b>ungroundable</b> question refuses or escalates — no invented answer.",
                "Escalations are visible (log / flag: topic, reason, timestamp) for a human expert to treat as ground truth later.",
            ]
        )
    )

    story.append(Paragraph("5. Contribution model", s["h1"]))
    story.append(
        table(
            ["Expert Scale", "Overtone"],
            [
                [
                    "Escalation rules + when “needs expert” is correct",
                    "Meet / Zoom / Teams join + presenter AV + voice relay",
                ],
                [
                    "Optional sample specialty scope (e.g. GTM-only) for the test",
                    "Indexed deck / session grounding + tool calls",
                ],
                [
                    "One short review call after you try Launch",
                    "Spike build + honest latency / failure notes",
                ],
            ],
            [3.25 * inch, 3.25 * inch],
        )
    )

    story.append(Paragraph("6. Suggested next steps", s["h1"]))
    story.append(
        bullets(
            [
                "You try <b>Launch</b> on the dashboard with your own Meet link (feedback welcome).",
                "We lock a <b>30-minute working session</b> to align escalate-stub fields with your handoff today.",
                "After one clean end-to-end run → decide commercial shape (integration / ongoing collab) — or stop cleanly.",
            ]
        )
    )

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.6, color=LINE))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "<b>Contact</b><br/>Muhammad Atif · Overtone · ranaatif1299@gmail.com<br/>"
            "Dashboard: https://overtone-dashboard-4idrhaffca-uc.a.run.app",
            s["small"],
        )
    )

    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=on_page)
    # rebuild with header on all content pages — cover has no header; page 1 is cover+content mixed
    # Simpler: add header on every page including first for this doc after cover height
    return path


def build_architecture():
    s = styles()
    path = OUT_DIR / "03_Overtone_Architecture_Overview.pdf"
    title = "Architecture Overview"

    def on_page(canvas, doc):
        header_footer(canvas, doc, title)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.75 * inch,
    )
    story = []
    cover_block(
        story,
        s,
        "Technical briefing — meeting join &amp; live grounding",
        "Architecture Overview",
        [
            "Audience: Technical partnership discussion",
            "Status: Active development — demo / architecture stage",
            "Date: August 2026",
            "Classification: Confidential — partner review",
        ],
    )

    story.append(Paragraph("1. Framing", s["h1"]))
    story.append(
        Paragraph(
            "Overtone is a <b>live meeting layer</b>: a bot joins Google Meet / Zoom / Teams as a participant, "
            "presents a deck, listens with realtime speech-to-speech, and answers from <b>indexed session sources</b> — "
            "with a design goal to <b>abstain or escalate</b> when grounding is weak (not invent).",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "It is <b>not</b> a finished “zero-hallucination guarantee” product. The honest framing is: "
            "<b>traceable, source-bound outputs + hard stop when the source cannot support an answer.</b>",
            s["body"],
        )
    )

    story.append(Paragraph("2. System context", s["h1"]))
    story.append(
        Paragraph(
            "Operator → Dashboard (upload &amp; launch) → Backend (FastAPI) → Recall.ai bot → Meeting room. "
            "Recall opens the Presenter UI as the bot camera. Presenter ↔ Backend over WebSocket (audio + tools). "
            "Backend ↔ Realtime voice (Gemini Live preferred / OpenAI Realtime). Backend reads slide index "
            "(pgvector), GCS artifacts, and Postgres session catalog.",
            s["body"],
        )
    )
    story.append(
        table(
            ["Component", "Role"],
            [
                ["Dashboard", "Upload decks, configure agents, launch bots into meetings"],
                ["Recall.ai", "Meeting participant join; virtual camera / audio path"],
                ["Presenter UI", "Deck display as bot camera; mic capture; play spoken audio"],
                ["Backend relay", "Session state, tool execution, voice bridge"],
                ["Realtime voice", "Speech-to-speech + function / tool calling"],
                ["pgvector + Vision", "Per-page extract, embed, retrieve grounded slide text"],
                ["GCS + Postgres", "Artifacts and durable session catalog"],
            ],
            [1.6 * inch, 4.9 * inch],
        )
    )

    story.append(Paragraph("3. Session lifecycle (summary)", s["h1"]))
    story.append(
        bullets(
            [
                "Upload PDF / PPTX → store → Vision extract per page → quality gate → embeddings → pgvector → status ready",
                "Launch: meeting URL + knowledge base → create session → Recall bot with output-media presenter URL",
                "Bot joins room → presenter WebSocket → Live voice session",
                "Participant audio → relay → model; model tool calls → navigate / get_slide_details / search → spoken answer from tool results only",
            ]
        )
    )

    story.append(Paragraph("4. Platform layers", s["h1"]))
    story.append(
        table(
            ["Layer", "Function", "Current technology"],
            [
                ["Capture / join", "Enter call as participant; camera shows slides", "Recall.ai"],
                ["Presenter", "Deck UI, mic, bot audio playback", "React (output-media page)"],
                ["Realtime voice", "Speech-to-speech + tools", "Gemini Live / OpenAI Realtime"],
                ["Orchestration", "State, tools, mute, page position", "FastAPI relay + executor"],
                ["Grounding", "Per-slide retrieval", "Vision → embeddings → pgvector"],
                ["Persistence", "Files, catalog, session extras", "GCS + Postgres"],
            ],
            [1.35 * inch, 2.4 * inch, 2.75 * inch],
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("5. Grounding path", s["h1"]))
    story.append(
        Paragraph(
            "User question → tool routing (navigate / get_slide_details / search) → indexed slide text + session page. "
            "Enough evidence → spoken answer. Insufficient evidence → abstain / clarify → escalate path (roadmap).",
            s["body"],
        )
    )
    story.append(Paragraph("Design principles (escalate-don’t-guess)", s["h2"]))
    story.append(
        bullets(
            [
                "Prefer the <b>currently visible slide</b> for “explain this / what’s on this.”",
                "Search the <b>deck index</b> before any external lookup.",
                "If retrieval is empty or stub-thin → <b>do not invent</b>; clarify or state not in source.",
                "<b>Human escalate</b> (expert as ground truth) is the intended next architectural step — not claimed as fully shipped today.",
            ]
        )
    )

    story.append(Paragraph("6. Indexing pipeline", s["h1"]))
    story.append(
        Paragraph(
            "Upload → store (GCS / local) → render page images → Vision per page → title / body / searchable_content → "
            "quality gate (reject stub pages) → embeddings → pgvector → presentation status ready. "
            "Vision stubs such as title-only “Slide 4” must not be marked ready.",
            s["body"],
        )
    )

    story.append(Paragraph("7. Realtime tools", s["h1"]))
    story.append(
        table(
            ["Tool", "Role"],
            [
                ["navigate_to_slide", "Jump to a page; persist current_page"],
                ["get_slide_details", "Narrate current or specified page from index"],
                ["search_and_answer", "Hybrid retrieve over slides; stay or navigate"],
                ["mute_self / unmute_self", "Hard silence path"],
                ["leave_call", "Explicit exit only"],
                ["fetch_external_data", "Last resort; not for on-deck questions"],
            ],
            [2.0 * inch, 4.5 * inch],
        )
    )
    story.append(
        Paragraph(
            "Spoken answers are instructed to come from <b>tool results</b> (slide_content / brief_content), not model memory.",
            s["body"],
        )
    )

    story.append(Paragraph("8. Maturity", s["h1"]))
    story.append(
        table(
            ["Solid enough to demonstrate", "Explicit next (roadmap)"],
            [
                [
                    "Join Meet via Recall; present deck as bot camera; realtime voice; tool-grounded slide Q&amp;A; index quality gate",
                    "First-class escalate-to-human queue; stronger abstention at tool boundary; multi-instance WS fan-out; claim→source audit trail",
                ]
            ],
            [3.25 * inch, 3.25 * inch],
        )
    )

    story.append(Paragraph("9. Fit with a digital protégé product", s["h1"]))
    story.append(
        table(
            ["Protégé concern", "Overtone role"],
            [
                ["Join Meet / Zoom as participant", "Meeting adapter (focus of current demos)"],
                ["Follow conversation without guessing", "Session + deck grounding + abstain"],
                ["Respond when addressed", "Realtime voice + tools"],
                ["Escalate when unsure", "Architectural fit — align with expert KB / human handoff"],
            ],
            [2.6 * inch, 3.9 * inch],
        )
    )
    story.append(
        Paragraph(
            "Overtone is best understood as a <b>live meeting adapter + grounding shell</b>, "
            "not a replacement for an expert-judgment knowledge system.",
            s["body"],
        )
    )

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.6, color=LINE))
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "This document describes current engineering architecture as of the date on the cover. "
            "Capabilities labeled roadmap are intentional design direction, not production guarantees.<br/><br/>"
            "<b>Contact:</b> Muhammad Atif · ranaatif1299@gmail.com",
            s["small"],
        )
    )

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return path


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = [build_cover_letter(), build_spike(), build_architecture()]
    for p in paths:
        print(p)


if __name__ == "__main__":
    main()
