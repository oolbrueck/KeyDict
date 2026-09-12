from __future__ import annotations

import subprocess
import unittest
from unittest.mock import call, patch

from keydict.output import _paste_shortcut


class OutputTests(unittest.TestCase):
    @patch("keydict.output.subprocess.run")
    @patch("keydict.output.shutil.which")
    def test_wayland_falls_back_from_wtype_to_ydotool(self, which, run) -> None:
        which.side_effect = lambda name: f"/usr/bin/{name}" if name in {"wtype", "ydotool"} else None
        run.side_effect = [subprocess.CalledProcessError(1, "wtype"), None]
        with patch.dict("keydict.output.os.environ", {"WAYLAND_DISPLAY": "wayland-0"}, clear=True):
            _paste_shortcut()
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0], call(["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"], check=True))
        self.assertEqual(
            run.call_args_list[1],
            call(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], check=True),
        )

    @patch("keydict.output.subprocess.run")
    @patch("keydict.output.shutil.which")
    def test_x11_uses_xdotool(self, which, run) -> None:
        which.side_effect = lambda name: "/usr/bin/xdotool" if name == "xdotool" else None
        with patch.dict("keydict.output.os.environ", {"DISPLAY": ":0"}, clear=True):
            _paste_shortcut()
        run.assert_called_once_with(["xdotool", "key", "--clearmodifiers", "ctrl+v"], check=True)


if __name__ == "__main__":
    unittest.main()

