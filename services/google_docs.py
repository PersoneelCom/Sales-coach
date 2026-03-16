from __future__ import annotations

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

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
        document = self.docs_service.documents().create(body={"title": title}).execute()
        document_id = document["documentId"]

        body_lines = [title, "", "Summary", ""]
        body_lines.extend(summary_markdown.strip().splitlines())
        body_lines.extend(["", "Transcript", ""])

        speaker_ranges = []
        summary_heading_start = len(title) + 3
        transcript_heading_start = sum(len(line) + 1 for line in body_lines[: len(body_lines) - 3]) + 2
        index_pointer = sum(len(line) + 1 for line in body_lines) + 1

        for segment in transcript["segments"]:
            speaker_line = f"{segment['speaker']} [{segment['start_label']}]"
            body_lines.append(speaker_line)
            speaker_ranges.append((index_pointer, index_pointer + len(speaker_line), "HEADING_2"))
            index_pointer += len(speaker_line) + 1

            body_lines.append(segment["text"])
            index_pointer += len(segment["text"]) + 1
            body_lines.append("")
            index_pointer += 1

        content = "\n".join(body_lines)
        requests = [
            {
                "insertText": {
                    "location": {"index": 1},
                    "text": content,
                }
            }
        ]

        title_end = 1 + len(title)
        requests.append(
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": 1, "endIndex": title_end},
                    "paragraphStyle": {"namedStyleType": "TITLE"},
                    "fields": "namedStyleType",
                }
            }
        )

        summary_start = summary_heading_start
        summary_end = summary_start + len("Summary")
        requests.append(
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": summary_start, "endIndex": summary_end},
                    "paragraphStyle": {"namedStyleType": "HEADING_1"},
                    "fields": "namedStyleType",
                }
            }
        )

        transcript_heading_end = transcript_heading_start + len("Transcript")
        requests.append(
            {
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": transcript_heading_start,
                        "endIndex": transcript_heading_end,
                    },
                    "paragraphStyle": {"namedStyleType": "HEADING_1"},
                    "fields": "namedStyleType",
                }
            }
        )

        for start, end, style in speaker_ranges:
            requests.append(
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "paragraphStyle": {"namedStyleType": style},
                        "fields": "namedStyleType",
                    }
                }
            )

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
