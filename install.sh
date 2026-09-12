#!/usr/bin/env bash
set -euo pipefail

KEYDICT_SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
KEYDICT_INSTALL_ROOT="${XDG_DATA_HOME:-${HOME}/.local/share}/keydict"
KEYDICT_BIN_DIR="${HOME}/.local/bin"
KEYDICT_CONFIG_FILE="${XDG_CONFIG_HOME:-${HOME}/.config}/keydict/config.toml"
KEYDICT_SYSTEMD_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
INSTALL_SYSTEM=true

usage() {
    echo "Usage: ./install.sh [--no-system-packages]"
    echo
    echo "Installiert KeyDict und standardmaessig alle benoetigten Linux-Pakete."
}

for keydict_arg in "$@"; do
    case "$keydict_arg" in
        --no-system-packages) INSTALL_SYSTEM=false ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unbekannte Option: $keydict_arg" >&2; usage >&2; exit 2 ;;
    esac
done

as_root() {
    if [[ "${EUID}" -eq 0 ]]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        echo "Fuer Systempakete wird sudo oder ein Root-Aufruf benoetigt." >&2
        exit 1
    fi
}

install_system_packages() {
    if command -v apt-get >/dev/null 2>&1; then
        echo "Installiere Abhaengigkeiten fuer Debian/Ubuntu …"
        as_root apt-get update
        as_root apt-get install -y \
            python3 python3-venv python3-dev build-essential portaudio19-dev \
            libnotify-bin wl-clipboard wtype ydotool xclip xdotool
    elif command -v dnf >/dev/null 2>&1; then
        echo "Installiere Abhaengigkeiten fuer Fedora …"
        as_root dnf install -y \
            python3 python3-devel gcc portaudio portaudio-devel \
            libnotify wl-clipboard wtype ydotool xclip xdotool
    elif command -v pacman >/dev/null 2>&1; then
        echo "Installiere Abhaengigkeiten fuer Arch Linux …"
        as_root pacman -S --needed --noconfirm \
            python base-devel portaudio libnotify wl-clipboard wtype ydotool xclip xdotool
    else
        echo "Kein unterstuetzter Paketmanager gefunden." >&2
        echo "Unterstuetzt werden apt, dnf und pacman. Nutze --no-system-packages" >&2
        echo "nachdem Python 3, PortAudio sowie Clipboard/Paste-Werkzeuge installiert wurden." >&2
        exit 1
    fi
}

if [[ "$INSTALL_SYSTEM" == true ]]; then
    install_system_packages
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 wurde nicht gefunden." >&2
    exit 1
fi

echo "Installiere KeyDict nach $KEYDICT_INSTALL_ROOT …"
mkdir -p "$KEYDICT_INSTALL_ROOT" "$KEYDICT_BIN_DIR" "$KEYDICT_SYSTEMD_DIR"
python3 -m venv "$KEYDICT_INSTALL_ROOT/venv"
"$KEYDICT_INSTALL_ROOT/venv/bin/python" -m pip install --upgrade pip
"$KEYDICT_INSTALL_ROOT/venv/bin/pip" install --upgrade "$KEYDICT_SOURCE_DIR"
ln -sfn "$KEYDICT_INSTALL_ROOT/venv/bin/keydict" "$KEYDICT_BIN_DIR/keydict"
install -m 0644 "$KEYDICT_SOURCE_DIR/keydict.service" "$KEYDICT_SYSTEMD_DIR/keydict.service"

if [[ ! -e "$KEYDICT_CONFIG_FILE" ]]; then
    "$KEYDICT_BIN_DIR/keydict" init
else
    echo "Bestehende Konfiguration bleibt unveraendert: $KEYDICT_CONFIG_FILE"
fi

if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload || true
fi

echo
echo "KeyDict wurde installiert."
echo "1. Bearbeite: $KEYDICT_CONFIG_FILE"
echo "2. Setze dort den API-Key oder exportiere OPENAI_API_KEY."
echo "3. Starte mit: keydict run"
if [[ ":${PATH}:" != *":${KEYDICT_BIN_DIR}:"* ]]; then
    echo "Hinweis: Fuege $KEYDICT_BIN_DIR zu PATH hinzu oder melde dich neu an."
fi
