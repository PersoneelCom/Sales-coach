from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from services.analysis_utils import extract_score_value, markdown_section_items, split_markdown_sections, top_section_items


ACCENT = colors.HexColor("#B55A34")
DEEP = colors.HexColor("#204F5A")
INK = colors.HexColor("#1E1C1A")
MUTED = colors.HexColor("#6B6359")
PANEL = colors.HexColor("#FFF8F0")
PANEL_ALT = colors.HexColor("#F3EEE7")
LINE = colors.HexColor("#E5D5C7")
OBJECTION_BG = colors.HexColor("#FFF1EA")
COACH_BG = colors.HexColor("#EEF7F5")
GOOD = colors.HexColor("#2E7D5B")
MID = colors.HexColor("#D18D31")
LOW = colors.HexColor("#B5483C")


def _build_styles():
    base = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "SalesCoachEyebrow",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=ACCENT,
            spaceAfter=7,
        ),
        "title": ParagraphStyle(
            "SalesCoachTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=32,
            textColor=INK,
            spaceAfter=10,
        ),
        "lead": ParagraphStyle(
            "SalesCoachLead",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=MUTED,
            spaceAfter=10,
        ),
        "micro": ParagraphStyle(
            "SalesCoachMicro",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=MUTED,
        ),
        "section": ParagraphStyle(
            "SalesCoachSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=DEEP,
            spaceBefore=14,
            spaceAfter=7,
        ),
        "section_alt": ParagraphStyle(
            "SalesCoachSectionAlt",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=ACCENT,
            spaceBefore=14,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "SalesCoachBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "speaker": ParagraphStyle(
            "SalesCoachSpeaker",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=ACCENT,
            spaceAfter=2,
        ),
        "callout_title": ParagraphStyle(
            "SalesCoachCalloutTitle",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=INK,
            spaceAfter=5,
        ),
        "callout_body": ParagraphStyle(
            "SalesCoachCalloutBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.7,
            leading=14,
            textColor=INK,
            spaceAfter=3,
        ),
        "score_big": ParagraphStyle(
            "SalesCoachScoreBig",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=28,
            textColor=INK,
            alignment=TA_LEFT,
        ),
    }


def _bullet_list(items: list[str], styles: dict) -> ListFlowable:
    bullet_items = [ListItem(Paragraph(escape(item), styles["body"]), leftIndent=0, value="bullet") for item in items]
    return ListFlowable(
        bullet_items,
        bulletType="bullet",
        start="circle",
        leftIndent=16,
        bulletFontName="Helvetica",
        bulletFontSize=8,
    )


def _section_block(title: str, body: str, styles: dict, background_color=None) -> list:
    items = markdown_section_items(body)
    heading_style = styles["section_alt"] if title in {"Objections", "Coaching Tips"} else styles["section"]
    if background_color:
        table_rows = [[Paragraph(escape(title), heading_style)]]
        if items:
            table_rows.append([_bullet_list(items, styles)])
        else:
            table_rows.append([Paragraph("No signal captured for this section.", styles["body"])])
        table = Table(table_rows, colWidths=[174 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), background_color),
                    ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                    ("PADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        return [Spacer(1, 4), table]

    story = [Paragraph(escape(title), heading_style)]
    if not items:
        story.append(Paragraph("No signal captured for this section.", styles["body"]))
        return story
    story.append(_bullet_list(items, styles))
    return story


def _stat_table(call_type: str, score_display: str, language: str, duration_minutes: float, segment_count: int):
    table = Table(
        [
            ["Call Type", call_type],
            ["Call Score", score_display],
            ["Language", language],
            ["Duration", f"{duration_minutes} min"],
            ["Segments", str(segment_count)],
        ],
        colWidths=[38 * mm, 46 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PANEL_ALT),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _score_color(score_value):
    if score_value is None:
        return MUTED
    if score_value >= 8:
        return GOOD
    if score_value >= 6:
        return MID
    return LOW


def _page_chrome(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(doc.leftMargin, height - 12 * mm, width - doc.rightMargin, height - 12 * mm)
    canvas.line(doc.leftMargin, 11 * mm, width - doc.rightMargin, 11 * mm)
    canvas.setFillColor(ACCENT)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(doc.leftMargin, height - 9 * mm, "Personeel.com | Sales Coach")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - doc.rightMargin, height - 9 * mm, "Premium Call Review")
    canvas.drawString(doc.leftMargin, 7 * mm, "Generated by Sales Coach")
    canvas.drawRightString(width - doc.rightMargin, 7 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_transcript_pdf(title: str, summary_markdown: str, transcript: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=title,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = _build_styles()
    sections = split_markdown_sections(summary_markdown)
    score_value = extract_score_value(sections.get("Call Score", ""))
    call_type = sections.get("Call Type", "Unknown")
    duration_seconds = transcript.get("duration_seconds") or 0
    duration_minutes = round(duration_seconds / 60, 1)
    score_display = f"{score_value}/10" if score_value is not None else "Pending"
    score_color = _score_color(score_value)
    coaching_points = top_section_items(sections.get("Coaching Tips", ""), limit=3)
    objection_points = top_section_items(sections.get("Objections", ""), limit=2)

    story = [
        Paragraph("Sales Coach Report", styles["eyebrow"]),
        Paragraph(escape(title), styles["title"]),
        Paragraph(
            "A premium export of the call review, including structure, coaching, objections, score, and the full transcript.",
            styles["lead"],
        ),
    ]

    summary_line = markdown_section_items(sections.get("Call Summary", ""))
    hero_table = Table(
        [
            [
                [
                    Paragraph("Overview", styles["section_alt"]),
                    Paragraph(
                        escape(summary_line[0])
                        if summary_line
                        else "No summary captured yet.",
                        styles["lead"],
                    ),
                ],
                _stat_table(
                    call_type=call_type,
                    score_display=score_display,
                    language=transcript.get("language", "unknown"),
                    duration_minutes=duration_minutes,
                    segment_count=len(transcript["segments"]),
                ),
            ]
        ],
        colWidths=[104 * mm, 70 * mm],
    )
    hero_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), PANEL),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#FFF2E7")),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.extend([hero_table, Spacer(1, 8)])

    score_card = Table(
        [
            [
                Paragraph("Overall Score", styles["micro"]),
                Paragraph(f'<font color="{score_color}">{escape(score_display)}</font>', styles["score_big"]),
                Paragraph(escape(call_type), styles["lead"]),
            ]
        ],
        colWidths=[34 * mm, 34 * mm, 106 * mm],
    )
    score_card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, score_color),
                ("PADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.extend([score_card, Spacer(1, 8)])

    highlight_rows = []
    if coaching_points:
        highlight_rows.append(
            [
                Paragraph("Top Coaching Points", styles["callout_title"]),
                Paragraph("<br/>".join(f"• {escape(item)}" for item in coaching_points), styles["callout_body"]),
            ]
        )
    if objection_points:
        highlight_rows.append(
            [
                Paragraph("Key Objections", styles["callout_title"]),
                Paragraph("<br/>".join(f"• {escape(item)}" for item in objection_points), styles["callout_body"]),
            ]
        )
    if highlight_rows:
        highlights = Table(highlight_rows, colWidths=[46 * mm, 128 * mm])
        highlights.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                    ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                    ("PADDING", (0, 0), (-1, -1), 10),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.extend([highlights, Spacer(1, 8)])

    story.append(HRFlowable(color=LINE, width="100%"))

    ordered_sections = [
        "Conversation Structure",
        "Questions Asked",
        "Key Pain Points",
        "Objections",
        "Coaching Tips",
        "Decision Signals",
        "Next Steps",
        "Call Score",
    ]

    if "Call Summary" in sections:
        story.extend(_section_block("Call Summary", sections["Call Summary"], styles))

    for section_name in ordered_sections:
        if section_name not in sections:
            continue
        background = None
        if section_name == "Objections":
            background = OBJECTION_BG
        elif section_name == "Coaching Tips":
            background = COACH_BG
        story.extend(_section_block(section_name, sections[section_name], styles, background_color=background))

    story.extend([Spacer(1, 10), Paragraph("Transcript", styles["section"])])

    for segment in transcript["segments"]:
        speaker_line = f"{segment['speaker']} [{segment['start_label']}]"
        segment_table = Table(
            [
                [Paragraph(escape(speaker_line), styles["speaker"])],
                [Paragraph(escape(segment["text"]), styles["body"])],
            ],
            colWidths=[174 * mm],
        )
        segment_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                    ("PADDING", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.extend([segment_table, Spacer(1, 6)])

    doc.build(story, onFirstPage=_page_chrome, onLaterPages=_page_chrome)
    return buffer.getvalue()
