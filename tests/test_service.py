from __future__ import annotations

import socket
import unittest
from unittest.mock import patch

from keydict.service import KeyDictService


class ServiceTests(unittest.TestCase):
    def test_windows_control_socket_uses_loopback_tcp(self) -> None:
        service = object.__new__(KeyDictService)
        with patch("keydict.service.sys.platform", "win32"), patch(
            "keydict.service.WINDOWS_CONTROL_ADDRESS", ("127.0.0.1", 0)
        ):
            server, cleanup_path = service._create_control_socket()
        self.addCleanup(server.close)
        self.assertEqual(server.family, socket.AF_INET)
        self.assertIsNone(cleanup_path)
        self.assertEqual(server.getsockname()[0], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
