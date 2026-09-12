from __future__ import annotations

import os
import shutil
import subprocess
import time

from .config import OutputConfig


class OutputError(RuntimeError):
    pass


def _run_with_input(command: list[str], text: str) -> None:
    try:
        subprocess.run(command, input=text.encode(), check=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as exc:
        raise OutputError(f"Befehl fehlgeschlagen: {' '.join(command)}: {exc}") from exc


def copy_to_clipboard(text: str) -> None:
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    errors: list[str] = []
    if wayland and shutil.which("wl-copy"):
        try:
            _run_with_input(["wl-copy"], text)
            return
        except OutputError as exc:
            errors.append(str(exc))
    if shutil.which("xclip"):
        try:
            _run_with_input(["xclip", "-selection", "clipboard"], text)
            return
        except OutputError as exc:
            errors.append(str(exc))
    if shutil.which("xsel"):
        try:
            _run_with_input(["xsel", "--clipboard", "--input"], text)
            return
        except OutputError as exc:
            errors.append(str(exc))
    detail = f" Versuche: {'; '.join(errors)}" if errors else ""
    raise OutputError(
        "Kein Zwischenablage-Werkzeug gefunden. Installiere 'wl-clipboard' (Wayland) "
        f"oder 'xclip' (X11).{detail}"
    )


def _paste_shortcut() -> None:
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    errors: list[str] = []
    if wayland and shutil.which("wtype"):
        try:
            subprocess.run(["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"], check=True)
            return
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"wtype: {exc}")
    if wayland and shutil.which("ydotool"):
        try:
            # Linux input key codes: LEFTCTRL=29, V=47; 1=down, 0=up.
            subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], check=True)
            return
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"ydotool: {exc}")
    if shutil.which("xdotool"):
        try:
            subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], check=True)
            return
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"xdotool: {exc}")
    detail = f" Versuche: {'; '.join(errors)}" if errors else ""
    raise OutputError(
        "Text wurde kopiert, aber kein Paste-Werkzeug gefunden. Installiere 'wtype' "
        f"oder 'ydotool' (Wayland), beziehungsweise 'xdotool' (X11).{detail}"
    )


def deliver(text: str, config: OutputConfig) -> None:
    copy_to_clipboard(text)
    if config.mode == "paste":
        time.sleep(max(config.paste_delay_ms, 0) / 1000)
        try:
            _paste_shortcut()
        except (OSError, subprocess.SubprocessError) as exc:
            raise OutputError(f"Text wurde kopiert, aber Einfuegen schlug fehl: {exc}") from exc
