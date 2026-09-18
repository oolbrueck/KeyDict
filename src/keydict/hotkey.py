from __future__ import annotations

import logging
import os
import re
import select
import sys
from collections.abc import Callable
from typing import Any

if sys.platform.startswith("linux"):
    try:
        from evdev import InputDevice, ecodes, list_devices
    except ImportError:  # pragma: no cover - reported when the backend is selected
        InputDevice = None  # type: ignore[assignment,misc]
        ecodes = None  # type: ignore[assignment]
        list_devices = None  # type: ignore[assignment]
else:
    InputDevice = None  # type: ignore[assignment,misc]
    ecodes = None  # type: ignore[assignment]
    list_devices = None  # type: ignore[assignment]

from .config import HotkeyConfig

LOG = logging.getLogger(__name__)

_ALIASES = {
    "CTRL": "KEY_LEFTCTRL",
    "LEFTCTRL": "KEY_LEFTCTRL",
    "RIGHTCTRL": "KEY_RIGHTCTRL",
    "ALT": "KEY_LEFTALT",
    "LEFTALT": "KEY_LEFTALT",
    "RIGHTALT": "KEY_RIGHTALT",
    "SHIFT": "KEY_LEFTSHIFT",
    "LEFTSHIFT": "KEY_LEFTSHIFT",
    "RIGHTSHIFT": "KEY_RIGHTSHIFT",
    "SUPER": "KEY_LEFTMETA",
    "META": "KEY_LEFTMETA",
    "SPACE": "KEY_SPACE",
    "ENTER": "KEY_ENTER",
    "ESC": "KEY_ESC",
}


class HotkeyError(RuntimeError):
    pass


def parse_hotkey(value: str) -> frozenset[int]:
    if ecodes is None:
        raise HotkeyError("Der evdev-Hotkey ist nur unter Linux verfuegbar")
    codes: set[int] = set()
    for raw_part in value.upper().replace(" ", "").split("+"):
        name = _ALIASES.get(
            raw_part, raw_part if raw_part.startswith("KEY_") else f"KEY_{raw_part}"
        )
        code = getattr(ecodes, name, None)
        if not isinstance(code, int):
            raise HotkeyError(f"Unbekannte Taste in [hotkey].key: {raw_part!r}")
        codes.add(code)
    if not codes:
        raise HotkeyError("[hotkey].key ist leer")
    return frozenset(codes)


class EvdevHotkey:
    def __init__(
        self,
        config: HotkeyConfig,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ):
        self.config = config
        self.on_press = on_press
        self.on_release = on_release
        self.codes = parse_hotkey(config.key)
        self._devices: list[Any] = []

    def _open_devices(self) -> list[Any]:
        if InputDevice is None or list_devices is None or ecodes is None:
            raise HotkeyError("Der evdev-Hotkey ist nur unter Linux verfuegbar")
        devices: list[Any] = []
        denied: list[str] = []
        for path in list_devices():
            try:
                device = InputDevice(path)
                capabilities = device.capabilities().get(ecodes.EV_KEY, [])
                if not self.codes.intersection(capabilities):
                    device.close()
                    continue
                if (
                    self.config.device
                    and self.config.device.lower() not in device.name.lower()
                ):
                    device.close()
                    continue
                devices.append(device)
            except PermissionError:
                denied.append(path)
        if not devices:
            suffix = ""
            if denied:
                suffix = (
                    " Keine Leserechte auf Eingabegeraete. Fuege den Benutzer zur Gruppe "
                    "'input' hinzu und melde dich neu an, oder nutze backend='external'."
                )
            raise HotkeyError("Keine passende Tastatur gefunden." + suffix)
        return devices

    def run(self) -> None:
        self._devices = self._open_devices()
        LOG.info(
            "Hotkey %s aktiv auf: %s",
            self.config.key,
            ", ".join(d.name for d in self._devices),
        )
        pressed: set[int] = set()
        active = False
        while True:
            readable, _, _ = select.select(self._devices, [], [])
            for device in readable:
                try:
                    events = device.read()
                except OSError:
                    continue
                for event in events:
                    if event.type != ecodes.EV_KEY:
                        continue
                    if event.value == 1:
                        pressed.add(event.code)
                    elif event.value == 0:
                        pressed.discard(event.code)
                    now_active = self.codes.issubset(pressed)
                    if now_active and not active:
                        active = True
                        self.on_press()
                    elif active and not now_active:
                        active = False
                        self.on_release()


def _pynput_key_names(value: str) -> frozenset[str]:
    names: set[str] = set()
    aliases = {
        "CTRL": "ctrl_l",
        "LEFTCTRL": "ctrl_l",
        "RIGHTCTRL": "ctrl_r",
        "ALT": "alt_l",
        "LEFTALT": "alt_l",
        "RIGHTALT": "alt_r",
        "SHIFT": "shift_l",
        "LEFTSHIFT": "shift_l",
        "RIGHTSHIFT": "shift_r",
        "SUPER": "cmd_l",
        "META": "cmd_l",
        "SPACE": "space",
        "ENTER": "enter",
        "ESC": "esc",
        "ESCAPE": "esc",
        "WIN": "cmd_l",
        "WINDOWS": "cmd_l",
        "DEL": "delete",
        "PAGEUP": "page_up",
        "PAGEDOWN": "page_down",
        "CAPSLOCK": "caps_lock",
        "BACKSPACE": "backspace",
        "TAB": "tab",
    }
    special_names = {
        "alt_l",
        "alt_r",
        "backspace",
        "caps_lock",
        "cmd_l",
        "cmd_r",
        "ctrl_l",
        "ctrl_r",
        "delete",
        "down",
        "end",
        "enter",
        "esc",
        "home",
        "insert",
        "left",
        "menu",
        "num_lock",
        "page_down",
        "page_up",
        "pause",
        "print_screen",
        "right",
        "scroll_lock",
        "shift_l",
        "shift_r",
        "space",
        "tab",
        "up",
    }
    for raw_part in value.upper().replace(" ", "").split("+"):
        if not raw_part:
            continue
        normalized = raw_part.removeprefix("KEY_")
        name = aliases.get(normalized, normalized.lower())
        if not (
            len(name) == 1
            or name in special_names
            or re.fullmatch(r"f(?:[1-9]|1[0-9]|2[0-4])", name)
        ):
            raise HotkeyError(f"Unbekannte Taste in [hotkey].key: {raw_part!r}")
        names.add(name)
    if not names:
        raise HotkeyError("[hotkey].key ist leer")
    return frozenset(names)


class PynputHotkey:
    def __init__(
        self,
        config: HotkeyConfig,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ):
        self.config = config
        self.on_press = on_press
        self.on_release = on_release
        self.names = _pynput_key_names(config.key)

    @staticmethod
    def available() -> bool:
        if sys.platform == "win32":
            return True
        return (
            bool(os.environ.get("DISPLAY"))
            and os.environ.get("XDG_SESSION_TYPE", "x11").lower() != "wayland"
        )

    @staticmethod
    def _name(key) -> str | None:  # noqa: ANN001
        char = getattr(key, "char", None)
        if char:
            return str(char).lower()
        name = getattr(key, "name", None)
        return str(name).lower() if name else None

    def run(self) -> None:
        if not self.available():
            raise HotkeyError("Kein unterstuetztes Desktop-Hotkey-System gefunden")
        try:
            from pynput import keyboard
        except Exception as exc:
            raise HotkeyError(
                f"Desktop-Hotkey konnte nicht geladen werden: {exc}"
            ) from exc

        pressed: set[str] = set()
        active = False

        def press(key) -> None:  # noqa: ANN001
            nonlocal active
            name = self._name(key)
            if name:
                pressed.add(name)
            now_active = self.names.issubset(pressed)
            if now_active and not active:
                active = True
                self.on_press()

        def release(key) -> None:  # noqa: ANN001
            nonlocal active
            name = self._name(key)
            if name:
                pressed.discard(name)
            now_active = self.names.issubset(pressed)
            if active and not now_active:
                active = False
                self.on_release()

        backend_name = "Windows" if sys.platform == "win32" else "X11"
        LOG.info("Hotkey %s aktiv ueber %s", self.config.key, backend_name)
        try:
            with keyboard.Listener(on_press=press, on_release=release) as listener:
                listener.join()
        except Exception as exc:
            raise HotkeyError(f"Desktop-Hotkey fehlgeschlagen: {exc}") from exc


# Kept as a compatibility name for callers that selected the former X11 backend.
X11Hotkey = PynputHotkey
