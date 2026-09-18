from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from keydict.config import ConfigError, _default_config_path, load_config

VALID_CONFIG = """
[api]
url = "https://example.test/v1/audio/transcriptions"
api_key = "${KEYDICT_TEST_KEY}"
model = "whisper-test"

[hotkey]
key = "CTRL+ALT+D"
mode = "toggle"

[output]
mode = "clipboard"
"""


class ConfigTests(unittest.TestCase):
    def test_windows_default_config_uses_appdata(self) -> None:
        with patch("keydict.config.sys.platform", "win32"), patch.dict(
            os.environ, {"APPDATA": r"C:\Users\test\AppData\Roaming"}
        ):
            self.assertEqual(
                _default_config_path(),
                Path(r"C:\Users\test\AppData\Roaming") / "KeyDict" / "config.toml",
            )

    def write_config(self, text: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "config.toml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_load_and_expand_environment(self) -> None:
        path = self.write_config(VALID_CONFIG)
        with patch.dict(os.environ, {"KEYDICT_TEST_KEY": "secret"}):
            config = load_config(path)
        self.assertEqual(config.api.api_key, "secret")
        self.assertEqual(config.hotkey.mode, "toggle")
        self.assertEqual(config.output.mode, "clipboard")

    def test_missing_environment_variable_is_reported(self) -> None:
        path = self.write_config(VALID_CONFIG)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ConfigError, "KEYDICT_TEST_KEY"):
                load_config(path)

    def test_invalid_mode_is_rejected(self) -> None:
        path = self.write_config(VALID_CONFIG.replace('mode = "toggle"', 'mode = "wrong"', 1))
        with patch.dict(os.environ, {"KEYDICT_TEST_KEY": "secret"}):
            with self.assertRaisesRegex(ConfigError, "hotkey"):
                load_config(path)

    def test_direct_openai_key_accidentally_wrapped_as_variable(self) -> None:
        text = VALID_CONFIG.replace('"${KEYDICT_TEST_KEY}"', '"${sk-project-test}"')
        config = load_config(self.write_config(text))
        self.assertEqual(config.api.api_key, "sk-project-test")


if __name__ == "__main__":
    unittest.main()
