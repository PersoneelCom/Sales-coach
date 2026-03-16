from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from streamlit.errors import StreamlitSecretNotFoundError

from services import config


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_env = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.original_env)

    @patch("services.config.st.secrets", {"API_KEY": "from-secret"})
    def test_get_setting_prefers_streamlit_secrets(self) -> None:
        os.environ["API_KEY"] = "from-env"

        result = config.get_setting("API_KEY")

        self.assertEqual(result, "from-secret")

    @patch("services.config.st.secrets", {})
    def test_get_setting_falls_back_to_environment(self) -> None:
        os.environ["API_KEY"] = "from-env"

        result = config.get_setting("API_KEY")

        self.assertEqual(result, "from-env")

    @patch("services.config.st.secrets")
    def test_get_setting_handles_missing_secret_store(self, secrets_mock) -> None:
        secrets_mock.__contains__.side_effect = StreamlitSecretNotFoundError("missing")
        os.environ["API_KEY"] = "from-env"

        result = config.get_setting("API_KEY")

        self.assertEqual(result, "from-env")

    @patch("services.config.get_setting", return_value={"type": "service_account"})
    def test_get_json_setting_returns_existing_dict(self, get_setting_mock) -> None:
        result = config.get_json_setting("GOOGLE_SERVICE_ACCOUNT_JSON")

        self.assertEqual(result, {"type": "service_account"})
        get_setting_mock.assert_called_once_with("GOOGLE_SERVICE_ACCOUNT_JSON")

    @patch("services.config.get_setting", return_value='{"type": "service_account"}')
    def test_get_json_setting_parses_json_string(self, get_setting_mock) -> None:
        result = config.get_json_setting("GOOGLE_SERVICE_ACCOUNT_JSON")

        self.assertEqual(result, {"type": "service_account"})
        get_setting_mock.assert_called_once_with("GOOGLE_SERVICE_ACCOUNT_JSON")

    @patch("services.config.get_setting", return_value="")
    def test_get_json_setting_returns_none_for_empty_value(self, get_setting_mock) -> None:
        result = config.get_json_setting("GOOGLE_SERVICE_ACCOUNT_JSON")

        self.assertIsNone(result)
        get_setting_mock.assert_called_once_with("GOOGLE_SERVICE_ACCOUNT_JSON")


if __name__ == "__main__":
    unittest.main()
