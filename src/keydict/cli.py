from __future__ import annotations

import argparse
import importlib.resources
import logging
import sys
from pathlib import Path

from .config import DEFAULT_CONFIG, ConfigError, load_config
from .service import KeyDictService, send_trigger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keydict", description="Sprachdiktion fuer Linux")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Pfad zur TOML-Konfiguration")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("run", help="KeyDict im Vordergrund starten")
    commands.add_parser("init", help="Beispielkonfiguration anlegen")
    trigger = commands.add_parser("trigger", help="Laufende Instanz extern umschalten")
    trigger.add_argument("action", nargs="?", choices=("toggle", "press", "release"), default="toggle")
    return parser


def init_config(destination: Path) -> None:
    if destination.exists():
        raise ConfigError(f"Datei existiert bereits: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    template = importlib.resources.files("keydict").joinpath("config.example.toml").read_text(encoding="utf-8")
    destination.write_text(template, encoding="utf-8")
    destination.chmod(0o600)
    print(f"Konfiguration angelegt: {destination}")


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "init":
            init_config(args.config)
            return
        if args.command == "trigger":
            send_trigger(args.action)
            return
        config = load_config(args.config)
        logging.basicConfig(
            level=getattr(logging, config.general.log_level, logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        KeyDictService(config).run()
    except (ConfigError, RuntimeError, KeyboardInterrupt) as exc:
        if not isinstance(exc, KeyboardInterrupt):
            print(f"keydict: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
