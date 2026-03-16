from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.google_docs import GOOGLE_SCOPES, GoogleDocsExporter, GoogleDocsSetupError


class GoogleDocsExporterInitTests(unittest.TestCase):
    @patch("services.google_docs.get_json_setting", return_value=None)
    def test_init_requires_service_account_json(self, get_json_setting_mock: MagicMock) -> None:
        with self.assertRaises(GoogleDocsSetupError):
            GoogleDocsExporter()

        get_json_setting_mock.assert_called_once_with("GOOGLE_SERVICE_ACCOUNT_JSON")

    @patch("services.google_docs.build")
    @patch("services.google_docs.Credentials.from_service_account_info", return_value="creds")
    @patch("services.google_docs.get_setting", side_effect=["share@example.com", "folder-123"])
    @patch("services.google_docs.get_json_setting", return_value={"type": "service_account"})
    def test_init_builds_docs_and_drive_clients(
        self,
        get_json_setting_mock: MagicMock,
        get_setting_mock: MagicMock,
        credentials_mock: MagicMock,
        build_mock: MagicMock,
    ) -> None:
        build_mock.side_effect = ["docs-service", "drive-service"]

        exporter = GoogleDocsExporter()

        self.assertEqual(exporter.docs_service, "docs-service")
        self.assertEqual(exporter.drive_service, "drive-service")
        self.assertEqual(exporter.share_email, "share@example.com")
        self.assertEqual(exporter.folder_id, "folder-123")
        credentials_mock.assert_called_once_with({"type": "service_account"}, scopes=GOOGLE_SCOPES)
        self.assertEqual(build_mock.call_args_list[0].args, ("docs", "v1"))
        self.assertEqual(build_mock.call_args_list[1].args, ("drive", "v3"))
        self.assertEqual(get_setting_mock.call_args_list[0].args, ("GOOGLE_DOC_SHARE_EMAIL",))
        self.assertEqual(get_setting_mock.call_args_list[1].args, ("GOOGLE_DRIVE_FOLDER_ID",))
        get_json_setting_mock.assert_called_once_with("GOOGLE_SERVICE_ACCOUNT_JSON")


class GoogleDocsExporterCreateDocumentTests(unittest.TestCase):
    def _build_exporter(self, share_email: str | None = "share@example.com", folder_id: str | None = "folder-123") -> GoogleDocsExporter:
        exporter = object.__new__(GoogleDocsExporter)
        exporter.docs_service = MagicMock()
        exporter.drive_service = MagicMock()
        exporter.share_email = share_email
        exporter.folder_id = folder_id
        exporter.docs_service.documents.return_value.create.return_value.execute.return_value = {"documentId": "doc-123"}
        return exporter

    def test_create_document_builds_content_and_updates_permissions(self) -> None:
        exporter = self._build_exporter()
        transcript = {
            "segments": [
                {"speaker": "You", "start_label": "00:00", "text": "Hello"},
                {"speaker": "Prospect", "start_label": "00:05", "text": "Need pricing"},
            ]
        }

        url = exporter.create_document(
            title="Sales Coach - Call",
            summary_markdown="## Call Summary\n- Good fit",
            transcript=transcript,
        )

        self.assertEqual(url, "https://docs.google.com/document/d/doc-123/edit")
        exporter.docs_service.documents.return_value.create.assert_called_once_with(
            body={"title": "Sales Coach - Call"}
        )
        batch_call = exporter.docs_service.documents.return_value.batchUpdate.call_args
        self.assertEqual(batch_call.kwargs["documentId"], "doc-123")
        requests = batch_call.kwargs["body"]["requests"]
        self.assertEqual(requests[0]["insertText"]["location"], {"index": 1})
        self.assertIn("Sales Coach - Call", requests[0]["insertText"]["text"])
        self.assertIn("Summary", requests[0]["insertText"]["text"])
        self.assertIn("Transcript", requests[0]["insertText"]["text"])
        self.assertIn("Prospect [00:05]", requests[0]["insertText"]["text"])
        exporter.drive_service.files.return_value.update.assert_called_once_with(
            fileId="doc-123",
            addParents="folder-123",
            fields="id, parents",
        )
        exporter.drive_service.permissions.return_value.create.assert_called_once_with(
            fileId="doc-123",
            body={"type": "user", "role": "writer", "emailAddress": "share@example.com"},
            sendNotificationEmail=False,
        )

    def test_create_document_skips_drive_changes_when_not_configured(self) -> None:
        exporter = self._build_exporter(share_email=None, folder_id=None)

        exporter.create_document(
            title="Sales Coach - Call",
            summary_markdown="Summary",
            transcript={"segments": []},
        )

        exporter.drive_service.files.return_value.update.assert_not_called()
        exporter.drive_service.permissions.return_value.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
