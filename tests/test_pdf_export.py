from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.pdf_export import build_transcript_pdf


class PdfExportTests(unittest.TestCase):
    def test_build_transcript_pdf_returns_pdf_bytes(self) -> None:
        pdf_bytes = build_transcript_pdf(
            title="Sales Coach - Call",
            summary_markdown="## Call Summary\n- Ready to buy",
            transcript={"segments": [{"speaker": "You", "start_label": "00:00", "text": "Hello"}]},
        )

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 100)

    @patch("services.pdf_export.SimpleDocTemplate")
    @patch("services.pdf_export.Paragraph")
    @patch("services.pdf_export.Spacer")
    def test_build_transcript_pdf_escapes_summary_and_transcript_text(
        self,
        spacer_mock: MagicMock,
        paragraph_mock: MagicMock,
        simple_doc_template_mock: MagicMock,
    ) -> None:
        paragraph_mock.side_effect = lambda text, style: ("paragraph", text, style)
        spacer_mock.side_effect = lambda width, height: ("spacer", width, height)
        doc = MagicMock()
        simple_doc_template_mock.return_value = doc

        build_transcript_pdf(
            title="Sales Coach - <Call>",
            summary_markdown="Line & <one>\n\nLine > two",
            transcript={"segments": [{"speaker": "You", "start_label": "00:00", "text": "Body & <unsafe>"}]},
        )

        paragraph_texts = [call.args[0] for call in paragraph_mock.call_args_list]
        self.assertIn("Line &amp; &lt;one&gt;", paragraph_texts)
        self.assertIn("Line &gt; two", paragraph_texts)
        self.assertIn("Body &amp; &lt;unsafe&gt;", paragraph_texts)
        doc.build.assert_called_once()


if __name__ == "__main__":
    unittest.main()
