from __future__ import annotations

import os
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _default_config_path() -> Path:
    if sys.platform == "win32":
        config_root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return config_root / "KeyDict" / "config.toml"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "keydict" / "config.toml"


DEFAULT_CONFIG = _default_config_path()
_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)}")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ApiConfig:
    url: str
    api_key: str
    model: str
    language: str | None = None
    prompt: str | None = None
    timeout_seconds: float = 120


@dataclass(frozen=True)
class HotkeyConfig:
    key: str = "F8"
    mode: str = "hold"
    backend: str = "auto"
    device: str | None = None


@dataclass(frozen=True)
class AudioConfig:
    device: str | int | None = None
    channels: int = 1
    sample_rate: int = 0


@dataclass(frozen=True)
class OutputConfig:
    mode: str = "paste"
    paste_delay_ms: int = 120


@dataclass(frozen=True)
class GeneralConfig:
    notify: bool = True
    log_level: str = "INFO"


@dataclass(frozen=True)
class Config:
    api: ApiConfig
    hotkey: HotkeyConfig
    audio: AudioConfig
    output: OutputConfig
    general: GeneralConfig


def _expand_env(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in os.environ:
            raise ConfigError(f"Umgebungsvariable {name!r} ist nicht gesetzt")
        return os.environ[name]

    return _ENV_PATTERN.sub(replace, value)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"[{name}] muss eine TOML-Tabelle sein")
    return {key: _expand_env(item) for key, item in value.items()}


def load_config(path: Path) -> Config:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(
            f"Konfiguration nicht gefunden: {path}. Erzeuge sie mit: keydict init"
        ) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Ungueltiges TOML in {path}: {exc}") from exc

    api = _section(data, "api")
    hotkey = _section(data, "hotkey")
    audio = _section(data, "audio")
    output = _section(data, "output")
    general = _section(data, "general")

    for required in ("url", "api_key", "model"):
        if not api.get(required):
            raise ConfigError(f"[api].{required} fehlt oder ist leer")

    api_key = str(api["api_key"])
    # A direct OpenAI key is occasionally pasted into the environment-variable
    # placeholder as ${sk-...}. Accept that harmless formatting mistake.
    if api_key.startswith("${sk-") and api_key.endswith("}"):
        api_key = api_key[2:-1]

    hotkey_mode = str(hotkey.get("mode", "hold")).lower()
    if hotkey_mode not in {"hold", "toggle"}:
        raise ConfigError("[hotkey].mode muss 'hold' oder 'toggle' sein")
    backend = str(hotkey.get("backend", "auto")).lower()
    if backend not in {"auto", "evdev", "pynput", "x11", "windows", "external"}:
        raise ConfigError(
            "[hotkey].backend muss 'auto', 'evdev', 'pynput', 'x11', 'windows' oder 'external' sein"
        )
    output_mode = str(output.get("mode", "paste")).lower()
    if output_mode not in {"clipboard", "paste"}:
        raise ConfigError("[output].mode muss 'clipboard' oder 'paste' sein")

    device = audio.get("device")
    if isinstance(device, str) and device.isdigit():
        device = int(device)

    return Config(
        api=ApiConfig(
            url=str(api["url"]),
            api_key=api_key,
            model=str(api["model"]),
            language=str(api["language"]) if api.get("language") else None,
            prompt=str(api["prompt"]) if api.get("prompt") else None,
            timeout_seconds=float(api.get("timeout_seconds", 120)),
        ),
        hotkey=HotkeyConfig(
            key=str(hotkey.get("key", "F8")),
            mode=hotkey_mode,
            backend=backend,
            device=str(hotkey["device"]) if hotkey.get("device") else None,
        ),
        audio=AudioConfig(
            device=device,
            channels=int(audio.get("channels", 1)),
            sample_rate=int(audio.get("sample_rate", 0)),
        ),
        output=OutputConfig(
            mode=output_mode,
            paste_delay_ms=int(output.get("paste_delay_ms", 120)),
        ),
        general=GeneralConfig(
            notify=bool(general.get("notify", True)),
            log_level=str(general.get("log_level", "INFO")).upper(),
        ),
    )
