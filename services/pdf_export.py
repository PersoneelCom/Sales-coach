from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def build_transcript_pdf(title: str, summary_markdown: str, transcript: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=title)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12), Paragraph("Summary", styles["Heading1"])]

    for line in summary_markdown.strip().splitlines():
        safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if not safe_line.strip():
            story.append(Spacer(1, 8))
        else:
            story.append(Paragraph(safe_line, styles["BodyText"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Transcript", styles["Heading1"]))

    for segment in transcript["segments"]:
        speaker_line = f"{segment['speaker']} [{segment['start_label']}]"
        body_line = segment["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(speaker_line, styles["Heading2"]))
        story.append(Paragraph(body_line, styles["BodyText"]))
        story.append(Spacer(1, 8))

    doc.build(story)
    return buffer.getvalue()
