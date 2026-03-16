from __future__ import annotations

import os
import unittest

from streamlit.testing.v1 import AppTest

from services.security import build_password_hash


class AppSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.password = "PenTest!123"
        cls.password_hash = build_password_hash(cls.password)

    def setUp(self) -> None:
        self.original_env = dict(os.environ)
        os.environ["AUTH_REQUIRED"] = "true"
        os.environ["APP_PASSWORD_HASH"] = self.password_hash
        os.environ["ALLOW_GOOGLE_EXPORT"] = "false"
        os.environ["MAX_UPLOAD_MB"] = "1"
        os.environ["MAX_AUDIO_MINUTES"] = "1"
        os.environ["PROCESS_COOLDOWN_SECONDS"] = "5"

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_authentication_required_before_controls_render(self) -> None:
        app = AppTest.from_file("app.py")

        app.run()

        self.assertEqual([item.value for item in app.subheader], ["Restricted Access", "How this MVP works", "Before first use", "Security defaults"])
        self.assertEqual([item.label for item in app.text_input], ["Access password"])
        self.assertEqual([item.label for item in app.button], ["Unlock"])

    def test_wrong_password_shows_error(self) -> None:
        app = AppTest.from_file("app.py")

        app.run()
        app.text_input[0].input("wrong-password")
        app.button[0].click()
        app.run()

        self.assertEqual([item.value for item in app.error], ["Invalid password."])

    def test_missing_password_hash_blocks_access(self) -> None:
        os.environ["APP_PASSWORD_HASH"] = ""
        app = AppTest.from_file("app.py")

        app.run()

        self.assertEqual(
            [item.value for item in app.error],
            ["Missing APP_PASSWORD_HASH. Configure a password hash before exposing this app."],
        )

    def test_correct_password_unlocks_processing_controls(self) -> None:
        app = AppTest.from_file("app.py")

        app.run()
        app.text_input[0].input(self.password)
        app.button[0].click()
        app.run()

        self.assertIn("Upload a WAV sales call", [item.proto.label for item in app.get("file_uploader")])
        self.assertEqual([item.label for item in app.text_input], ["Rename Speaker 1", "Rename Speaker 2"])

    def test_auth_disabled_shows_controls_without_login(self) -> None:
        os.environ["AUTH_REQUIRED"] = "false"
        os.environ["APP_PASSWORD_HASH"] = ""
        app = AppTest.from_file("app.py")

        app.run()

        self.assertIn("Upload a WAV sales call", [item.proto.label for item in app.get("file_uploader")])
        self.assertNotIn("Restricted Access", [item.value for item in app.subheader])


if __name__ == "__main__":
    unittest.main()
