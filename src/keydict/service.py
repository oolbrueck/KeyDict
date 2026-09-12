from __future__ import annotations

import json
import logging
import os
import socket
import threading
from pathlib import Path

from .audio import Recorder
from .config import Config
from .hotkey import EvdevHotkey, HotkeyError, X11Hotkey
from .output import deliver
from .transcribe import transcribe


LOG = logging.getLogger(__name__)


def socket_path() -> Path:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/keydict-{os.getuid()}"))
    if "XDG_RUNTIME_DIR" not in os.environ:
        runtime.mkdir(mode=0o700, exist_ok=True)
    return runtime / "keydict.sock"


def notify(summary: str, body: str, enabled: bool) -> None:
    if not enabled:
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

    def _create_control_socket(self) -> tuple[socket.socket, Path]:
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

    def _socket_server(self, server: socket.socket, path: Path) -> None:
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
            path.unlink(missing_ok=True)

    def run(self) -> None:
        server, path = self._create_control_socket()
        threading.Thread(target=self._socket_server, args=(server, path), daemon=True).start()
        LOG.info("KeyDict laeuft")
        if self.config.hotkey.backend == "external":
            LOG.info("Externer Hotkey-Modus; warte auf 'keydict trigger'")
            threading.Event().wait()
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
    path = socket_path()
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(str(path))
        client.sendall(command.encode())
        client.recv(256)
    except (FileNotFoundError, ConnectionRefusedError) as exc:
        raise RuntimeError("KeyDict laeuft nicht. Starte zuerst: keydict run") from exc
    finally:
        client.close()
