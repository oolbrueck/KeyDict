from __future__ import annotations

import unittest

try:
    from evdev import ecodes
except ImportError:
    ecodes = None

from keydict.hotkey import HotkeyError, _pynput_key_names, parse_hotkey


class HotkeyTests(unittest.TestCase):
    @unittest.skipIf(ecodes is None, "evdev is only installed on Linux")
    def test_function_key(self) -> None:
        self.assertEqual(parse_hotkey("F8"), frozenset({ecodes.KEY_F8}))

    @unittest.skipIf(ecodes is None, "evdev is only installed on Linux")
    def test_combination_and_aliases(self) -> None:
        self.assertEqual(
            parse_hotkey("ctrl + alt + d"),
            frozenset({ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTALT, ecodes.KEY_D}),
        )

    @unittest.skipIf(ecodes is None, "evdev is only installed on Linux")
    def test_unknown_key(self) -> None:
        with self.assertRaises(HotkeyError):
            parse_hotkey("NOT_A_REAL_KEY")

    def test_pynput_names_support_windows_aliases(self) -> None:
        self.assertEqual(
            _pynput_key_names("CTRL + WIN + PAGEUP"),
            frozenset({"ctrl_l", "cmd_l", "page_up"}),
        )

    def test_pynput_names_reject_unknown_key(self) -> None:
        with self.assertRaises(HotkeyError):
            _pynput_key_names("NOT_A_REAL_KEY")


if __name__ == "__main__":
    unittest.main()

