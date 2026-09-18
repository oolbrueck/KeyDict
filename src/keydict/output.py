from __future__ import annotations

import os
import shutil
import subprocess
import sys
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
    if sys.platform == "win32":
        _copy_to_windows_clipboard(text)
        return
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


def _copy_to_windows_clipboard(text: str) -> None:
    """Write Unicode text with the native API, without requiring a helper app."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]

    opened = False
    for _ in range(10):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.02)
    if not opened:
        raise OutputError("Windows-Zwischenablage konnte nicht geoeffnet werden")

    handle = None
    transferred = False
    try:
        if not user32.EmptyClipboard():
            raise ctypes.WinError(ctypes.get_last_error())
        data = (text + "\0").encode("utf-16-le")
        handle = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        target = kernel32.GlobalLock(handle)
        if not target:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            ctypes.memmove(target, data, len(data))
        finally:
            kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(13, handle):  # CF_UNICODETEXT
            raise ctypes.WinError(ctypes.get_last_error())
        transferred = True  # The clipboard now owns the memory handle.
    except OSError as exc:
        raise OutputError(f"Windows-Zwischenablage fehlgeschlagen: {exc}") from exc
    finally:
        user32.CloseClipboard()
        if handle and not transferred:
            kernel32.GlobalFree(handle)


def _paste_shortcut() -> None:
    if sys.platform == "win32":
        _windows_paste_shortcut()
        return
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


def _windows_paste_shortcut() -> None:
    """Send Ctrl+V to the foreground window using the native input API."""
    import ctypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    key_up = 0x0002
    try:
        user32.keybd_event(0x11, 0, 0, 0)  # VK_CONTROL down
        user32.keybd_event(0x56, 0, 0, 0)  # V down
        user32.keybd_event(0x56, 0, key_up, 0)
        user32.keybd_event(0x11, 0, key_up, 0)
    except OSError as exc:
        raise OutputError(f"Windows-Einfuegen fehlgeschlagen: {exc}") from exc


def deliver(text: str, config: OutputConfig) -> None:
    copy_to_clipboard(text)
    if config.mode == "paste":
        time.sleep(max(config.paste_delay_ms, 0) / 1000)
        try:
            _paste_shortcut()
        except (OSError, subprocess.SubprocessError) as exc:
            raise OutputError(f"Text wurde kopiert, aber Einfuegen schlug fehl: {exc}") from exc
