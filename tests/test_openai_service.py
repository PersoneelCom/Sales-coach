from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services import openai_service


class OpenAIServiceTests(unittest.TestCase):
    @patch("services.openai_service.get_setting", return_value=None)
    def test_get_client_requires_api_key(self, get_setting_mock: MagicMock) -> None:
        with self.assertRaises(openai_service.OpenAISetupError):
            openai_service._get_client()

        get_setting_mock.assert_called_once_with("OPENAI_API_KEY")

    def test_to_dict_handles_supported_input_types(self) -> None:
        class Dumpable:
            def model_dump(self) -> dict:
                return {"source": "model_dump"}

        class PairIterable:
            def __iter__(self):
                return iter([("source", "iterable")])

        self.assertEqual(openai_service._to_dict({"source": "dict"}), {"source": "dict"})
        self.assertEqual(openai_service._to_dict(Dumpable()), {"source": "model_dump"})
        self.assertEqual(openai_service._to_dict(PairIterable()), {"source": "iterable"})

    @patch("services.openai_service.merge_segments_into_transcript", return_value={"done": True})
    @patch("services.openai_service.get_setting", side_effect=["gpt-4o-transcribe-diarize"])
    @patch("services.openai_service._get_client")
    def test_transcribe_call_uses_diarized_json_and_chunking_for_diarize_models(
        self,
        get_client_mock: MagicMock,
        get_setting_mock: MagicMock,
        merge_mock: MagicMock,
    ) -> None:
        client = MagicMock()
        client.audio.transcriptions.create.return_value = {"segments": []}
        get_client_mock.return_value = client

        result = openai_service.transcribe_call("call.wav", b"audio")

        self.assertEqual(result, {"done": True})
        create_kwargs = client.audio.transcriptions.create.call_args.kwargs
        self.assertEqual(create_kwargs["model"], "gpt-4o-transcribe-diarize")
        self.assertEqual(create_kwargs["response_format"], "diarized_json")
        self.assertEqual(create_kwargs["chunking_strategy"], "auto")
        self.assertEqual(create_kwargs["file"].name, "call.wav")
        self.assertEqual(create_kwargs["file"].getvalue(), b"audio")
        merge_mock.assert_called_once_with({"segments": []})
        get_setting_mock.assert_called_once_with("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-transcribe-diarize")

    @patch("services.openai_service.merge_segments_into_transcript", return_value={"done": True})
    @patch("services.openai_service.get_setting", side_effect=["gpt-4o-transcribe"])
    @patch("services.openai_service._get_client")
    def test_transcribe_call_uses_json_for_non_diarize_models(
        self,
        get_client_mock: MagicMock,
        _get_setting_mock: MagicMock,
        _merge_mock: MagicMock,
    ) -> None:
        client = MagicMock()
        client.audio.transcriptions.create.return_value = {"segments": []}
        get_client_mock.return_value = client

        openai_service.transcribe_call("call.wav", b"audio")

        create_kwargs = client.audio.transcriptions.create.call_args.kwargs
        self.assertEqual(create_kwargs["response_format"], "json")
        self.assertNotIn("chunking_strategy", create_kwargs)

    @patch("services.openai_service.get_setting", return_value="gpt-4o-mini")
    @patch("services.openai_service._get_client")
    def test_summarize_call_sends_transcript_text_to_responses_api(
        self,
        get_client_mock: MagicMock,
        get_setting_mock: MagicMock,
    ) -> None:
        client = MagicMock()
        client.responses.create.return_value = SimpleNamespace(output_text="## Call Summary\n- done")
        get_client_mock.return_value = client
        transcript = {
            "segments": [
                {"speaker": "You", "start_label": "00:00", "text": "Intro"},
                {"speaker": "Prospect", "start_label": "00:05", "text": "Need pricing"},
            ]
        }

        result = openai_service.summarize_call(transcript)

        self.assertEqual(result, "## Call Summary\n- done")
        create_kwargs = client.responses.create.call_args.kwargs
        self.assertEqual(create_kwargs["model"], "gpt-4o-mini")
        self.assertIn("Write clean markdown with these exact sections", create_kwargs["input"][0]["content"])
        self.assertEqual(
            create_kwargs["input"][1]["content"],
            "You [00:00]: Intro\nProspect [00:05]: Need pricing",
        )
        get_setting_mock.assert_called_once_with("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()
