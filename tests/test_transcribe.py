from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from keydict.config import ApiConfig
from keydict.transcribe import TranscriptionError, transcribe


class TranscribeTests(unittest.TestCase):
    @patch("keydict.transcribe.requests.post")
    def test_authentication_error_does_not_include_response_body(self, post: Mock) -> None:
        post.return_value = Mock(ok=False, status_code=401, text="server echoed secret-key-fragment")
        config = ApiConfig("https://example.test", "secret-key", "model")
        with self.assertRaises(TranscriptionError) as raised:
            transcribe(b"wav", config)
        self.assertNotIn("secret", str(raised.exception))
        self.assertIn("Authentifizierung", str(raised.exception))


if __name__ == "__main__":
    unittest.main()

