from __future__ import annotations

import json
import logging
import os
import socket
import sys
import threading
from pathlib import Path

from .audio import Recorder
from .config import Config
from .hotkey import EvdevHotkey, HotkeyError, PynputHotkey, X11Hotkey
from .output import deliver
from .transcribe import transcribe

LOG = logging.getLogger(__name__)
WINDOWS_CONTROL_ADDRESS = ("127.0.0.1", 47653)


def socket_path() -> Path:
    if sys.platform == "win32":
        raise RuntimeError("Windows verwendet einen lokalen TCP-Steuerkanal")
    fallback = f"/tmp/keydict-{os.getuid()}"
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", fallback))
    if "XDG_RUNTIME_DIR" not in os.environ:
        runtime.mkdir(mode=0o700, exist_ok=True)
    return runtime / "keydict.sock"


def notify(summary: str, body: str, enabled: bool) -> None:
    if not enabled:
        return
    if sys.platform == "win32":
        try:
            from winotify import Notification

            Notification(app_id="KeyDict", title=summary, msg=body).show()
        except Exception:
            LOG.debug("Windows-Benachrichtigung fehlgeschlagen", exc_info=True)
        return
    try:
        import subprocess

        subprocess.Popen(
            ["notify-send", "--app-name=KeyDict", summary, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


class KeyDictService:
    def __init__(self, config: Config):
        self.config = config
        self.recorder = Recorder(config.audio)
        self._processing = False
        self._state_lock = threading.Lock()

    def start_recording(self) -> None:
        with self._state_lock:
            if self._processing or self.recorder.recording:
                return
            try:
                self.recorder.start()
            except Exception as exc:
                LOG.exception("Aufnahme konnte nicht gestartet werden")
                notify("KeyDict: Fehler", str(exc), self.config.general.notify)
                return
        LOG.info("Aufnahme gestartet")
        notify("KeyDict", "Aufnahme gestartet", self.config.general.notify)

    def stop_recording(self) -> None:
        with self._state_lock:
            if not self.recorder.recording:
                return
            audio = self.recorder.stop()
            if not audio:
                LOG.warning("Keine Audiodaten aufgenommen")
                return
            self._processing = True
        LOG.info("Aufnahme beendet; transkribiere …")
        notify("KeyDict", "Transkribiere …", self.config.general.notify)
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    def _process(self, audio: bytes) -> None:
        try:
            text = transcribe(audio, self.config.api)
            deliver(text, self.config.output)
            LOG.info("Text ausgegeben: %s", text)
            notify("KeyDict", "Text ausgegeben", self.config.general.notify)
        except Exception as exc:
            LOG.exception("Diktat fehlgeschlagen")
            notify("KeyDict: Fehler", str(exc), self.config.general.notify)
        finally:
            with self._state_lock:
                self._processing = False

    def trigger_press(self) -> None:
        if self.config.hotkey.mode == "toggle":
            if self.recorder.recording:
                self.stop_recording()
            else:
                self.start_recording()
        else:
            self.start_recording()

    def trigger_release(self) -> None:
        if self.config.hotkey.mode == "hold":
            self.stop_recording()

    def _create_control_socket(self) -> tuple[socket.socket, Path | None]:
        if sys.platform == "win32":
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                server.bind(WINDOWS_CONTROL_ADDRESS)
                server.listen(4)
            except OSError as exc:
                server.close()
                probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                probe.settimeout(0.25)
                try:
                    probe.connect(WINDOWS_CONTROL_ADDRESS)
                except OSError:
                    raise RuntimeError(f"Windows-Steuerkanal konnte nicht gestartet werden: {exc}") from exc
                finally:
                    probe.close()
                raise RuntimeError("Eine andere KeyDict-Instanz laeuft bereits") from exc
            return server, None

        path = socket_path()
        if path.exists():
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                probe.connect(str(path))
            except (ConnectionRefusedError, FileNotFoundError):
                path.unlink(missing_ok=True)
            else:
                raise RuntimeError("Eine andere KeyDict-Instanz laeuft bereits")
            finally:
                probe.close()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(str(path))
            path.chmod(0o600)
            server.listen(4)
        except Exception:
            server.close()
            raise
        return server, path

    def _socket_server(self, server: socket.socket, path: Path | None) -> None:
        try:
            while True:
                connection, _ = server.accept()
                with connection:
                    command = connection.recv(128).decode().strip()
                    if command == "toggle":
                        if self.recorder.recording:
                            self.stop_recording()
                        else:
                            self.start_recording()
                    elif command == "press":
                        self.trigger_press()
                    elif command == "release":
                        self.trigger_release()
                    connection.sendall(json.dumps({"ok": True}).encode())
        except Exception:
            LOG.exception("Steuer-Socket fehlgeschlagen")
        finally:
            server.close()
            if path is not None:
                path.unlink(missing_ok=True)

    def run(self) -> None:
        server, path = self._create_control_socket()
        threading.Thread(target=self._socket_server, args=(server, path), daemon=True).start()
        LOG.info("KeyDict laeuft")
        if self.config.hotkey.backend == "external":
            LOG.info("Externer Hotkey-Modus; warte auf 'keydict trigger'")
            threading.Event().wait()
            return
        if sys.platform == "win32":
            if self.config.hotkey.backend in {"evdev", "x11"}:
                raise HotkeyError(
                    f"Hotkey-Backend {self.config.hotkey.backend!r} ist unter Windows nicht verfuegbar; "
                    "verwende 'auto', 'windows', 'pynput' oder 'external'"
                )
            PynputHotkey(self.config.hotkey, self.trigger_press, self.trigger_release).run()
            return
        if self.config.hotkey.backend == "windows":
            raise HotkeyError("Hotkey-Backend 'windows' ist nur unter Windows verfuegbar")
        if self.config.hotkey.backend == "pynput":
            PynputHotkey(self.config.hotkey, self.trigger_press, self.trigger_release).run()
            return
        if self.config.hotkey.backend == "x11":
            X11Hotkey(self.config.hotkey, self.trigger_press, self.trigger_release).run()
            return
        try:
            EvdevHotkey(self.config.hotkey, self.trigger_press, self.trigger_release).run()
        except HotkeyError as exc:
            if self.config.hotkey.backend != "auto":
                raise
            LOG.warning("%s", exc)
        if X11Hotkey.available():
            try:
                X11Hotkey(self.config.hotkey, self.trigger_press, self.trigger_release).run()
                return
            except HotkeyError as exc:
                LOG.warning("%s", exc)
        LOG.warning("Wechsle zum externen Hotkey-Modus.")
        notify(
            "KeyDict: externer Hotkey-Modus",
            "Direkter Tastaturzugriff fehlt. Konfiguriere 'keydict trigger' als globales Tastaturkuerzel.",
            self.config.general.notify,
        )
        threading.Event().wait()


def send_trigger(command: str = "toggle") -> None:
    if sys.platform == "win32":
        address = WINDOWS_CONTROL_ADDRESS
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    else:
        address = str(socket_path())
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.settimeout(2)
        client.connect(address)
        client.sendall(command.encode())
        client.recv(256)
    except OSError as exc:
        raise RuntimeError("KeyDict laeuft nicht. Starte zuerst: keydict run") from exc
    finally:
        client.close()
