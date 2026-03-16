from __future__ import annotations

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from services.analysis_utils import extract_score_value, markdown_section_items, split_markdown_sections, top_section_items
from services.config import get_json_setting, get_setting


GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleDocsSetupError(RuntimeError):
    pass


class GoogleDocsExporter:
    def __init__(self) -> None:
        service_account_info = get_json_setting("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not service_account_info:
            raise GoogleDocsSetupError(
                "Google Docs export is not configured yet. Add GOOGLE_SERVICE_ACCOUNT_JSON to `.env` or Streamlit secrets."
            )

        credentials = Credentials.from_service_account_info(service_account_info, scopes=GOOGLE_SCOPES)
        self.docs_service = build("docs", "v1", credentials=credentials)
        self.drive_service = build("drive", "v3", credentials=credentials)
        self.share_email = get_setting("GOOGLE_DOC_SHARE_EMAIL")
        self.folder_id = get_setting("GOOGLE_DRIVE_FOLDER_ID")

    def create_document(self, title: str, summary_markdown: str, transcript: dict) -> str:
        sections = split_markdown_sections(summary_markdown)
        score_value = extract_score_value(sections.get("Call Score", ""))
        call_type = sections.get("Call Type", "Unknown")
        duration_seconds = transcript.get("duration_seconds") or 0
        duration_minutes = round(duration_seconds / 60, 1)
        score_display = f"{score_value}/10" if score_value is not None else "Pending"
        coaching_points = top_section_items(sections.get("Coaching Tips", ""), limit=3)
        objection_points = top_section_items(sections.get("Objections", ""), limit=2)

        body_lines = [
            title,
            "Sales Coach Report",
            "Premium call review export",
            "",
            "Overview",
            f"Call Type: {call_type}",
            f"Call Score: {score_display}",
            f"Language: {transcript.get('language', 'unknown')}",
            f"Duration: {duration_minutes} min",
            f"Segments: {len(transcript['segments'])}",
            "",
        ]

        if coaching_points:
            body_lines.append("Top Coaching Points")
            for item in coaching_points:
                body_lines.append(f"- {item}")
            body_lines.append("")

        if objection_points:
            body_lines.append("Key Objections")
            for item in objection_points:
                body_lines.append(f"- {item}")
            body_lines.append("")

        ordered_sections = [
            "Call Summary",
            "Conversation Structure",
            "Questions Asked",
            "Key Pain Points",
            "Objections",
            "Coaching Tips",
            "Decision Signals",
            "Next Steps",
            "Call Score",
        ]

        for section_name in ordered_sections:
            if section_name not in sections:
                continue
            body_lines.append(section_name)
            for item in markdown_section_items(sections[section_name]):
                body_lines.append(f"- {item}")
            body_lines.append("")

        body_lines.extend(["Transcript", ""])
        transcript_speaker_lines: list[str] = []
        for segment in transcript["segments"]:
            speaker_line = f"{segment['speaker']} [{segment['start_label']}]"
            transcript_speaker_lines.append(speaker_line)
            body_lines.append(speaker_line)
            body_lines.append(segment["text"])
            body_lines.append("")

        content = "".join(f"{line}\n" for line in body_lines)
        document = self.docs_service.documents().create(body={"title": title}).execute()
        document_id = document["documentId"]

        requests = [{"insertText": {"location": {"index": 1}, "text": content}}]
        pointer = 1
        heading_1_titles = ["Overview", "Top Coaching Points", "Key Objections", *ordered_sections, "Transcript"]

        for line in body_lines:
            start = pointer
            end = start + len(line)
            if not line:
                pointer = end + 1
                continue

            if line == title:
                requests.append(
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": start, "endIndex": end},
                            "textStyle": {
                                "bold": True,
                                "fontSize": {"magnitude": 24, "unit": "PT"},
                            },
                            "fields": "bold,fontSize",
                        }
                    }
                )
            elif line == "Sales Coach Report":
                requests.append(
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": start, "endIndex": end},
                            "textStyle": {
                                "foregroundColor": {
                                    "color": {"rgbColor": {"red": 0.71, "green": 0.35, "blue": 0.20}}
                                },
                                "bold": True,
                            },
                            "fields": "foregroundColor,bold",
                        }
                    }
                )
            elif line == "Premium call review export":
                requests.append(
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": start, "endIndex": end},
                            "textStyle": {
                                "foregroundColor": {
                                    "color": {"rgbColor": {"red": 0.42, "green": 0.39, "blue": 0.35}}
                                },
                                "italic": True,
                            },
                            "fields": "foregroundColor,italic",
                        }
                    }
                )
            elif line in heading_1_titles:
                requests.append(
                    {
                        "updateParagraphStyle": {
                            "range": {"startIndex": start, "endIndex": end},
                            "paragraphStyle": {"namedStyleType": "HEADING_1"},
                            "fields": "namedStyleType",
                        }
                    }
                )
            elif line in transcript_speaker_lines:
                requests.append(
                    {
                        "updateParagraphStyle": {
                            "range": {"startIndex": start, "endIndex": end},
                            "paragraphStyle": {"namedStyleType": "HEADING_2"},
                            "fields": "namedStyleType",
                        }
                    }
                )
            elif line.startswith("Call Type:") or line.startswith("Call Score:"):
                requests.append(
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": start, "endIndex": end},
                            "textStyle": {
                                "bold": True,
                                "foregroundColor": {
                                    "color": {"rgbColor": {"red": 0.13, "green": 0.31, "blue": 0.35}}
                                },
                            },
                            "fields": "bold,foregroundColor",
                        }
                    }
                )
            elif line.startswith("Language:") or line.startswith("Duration:") or line.startswith("Segments:"):
                requests.append(
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": start, "endIndex": end},
                            "textStyle": {
                                "foregroundColor": {
                                    "color": {"rgbColor": {"red": 0.42, "green": 0.39, "blue": 0.35}}
                                }
                            },
                            "fields": "foregroundColor",
                        }
                    }
                )
            pointer = end + 1

        self.docs_service.documents().batchUpdate(
            documentId=document_id,
            body={"requests": requests},
        ).execute()

        if self.folder_id:
            self.drive_service.files().update(
                fileId=document_id,
                addParents=self.folder_id,
                fields="id, parents",
            ).execute()

        if self.share_email:
            self.drive_service.permissions().create(
                fileId=document_id,
                body={"type": "user", "role": "writer", "emailAddress": self.share_email},
                sendNotificationEmail=False,
            ).execute()

        return f"https://docs.google.com/document/d/{document_id}/edit"
