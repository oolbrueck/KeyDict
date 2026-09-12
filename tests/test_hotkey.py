from __future__ import annotations

import unittest

from evdev import ecodes

from keydict.hotkey import HotkeyError, parse_hotkey


class HotkeyTests(unittest.TestCase):
    def test_function_key(self) -> None:
        self.assertEqual(parse_hotkey("F8"), frozenset({ecodes.KEY_F8}))

    def test_combination_and_aliases(self) -> None:
        self.assertEqual(
            parse_hotkey("ctrl + alt + d"),
            frozenset({ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTALT, ecodes.KEY_D}),
        )

    def test_unknown_key(self) -> None:
        with self.assertRaises(HotkeyError):
            parse_hotkey("NOT_A_REAL_KEY")


if __name__ == "__main__":
    unittest.main()

