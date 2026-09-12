# KeyDict

KeyDict ist ein konfigurierbares Linux-Diktierwerkzeug nach dem Push-to-talk-Prinzip. Eine globale Taste startet die Mikrofonaufnahme; nach dem Loslassen beziehungsweise dem zweiten Tastendruck wird die Aufnahme an einen OpenAI-kompatiblen Speech-to-text-Endpunkt geschickt. Das Ergebnis landet in der Zwischenablage oder direkt im aktiven Eingabefeld.

## Einfache Installation

Repository klonen und anschließend den Installer ausführen:

```bash
git clone https://github.com/oolbrueck/KeyDict.git
cd KeyDict
./install.sh
```

Der Installer erkennt Debian/Ubuntu, Fedora und Arch Linux. Er installiert Python, PortAudio und die benötigten X11-/Wayland-Helfer automatisch, richtet eine isolierte Python-Umgebung unter `~/.local/share/keydict` ein, legt `keydict` unter `~/.local/bin` ab und erzeugt die erste Konfiguration. Je nach Distribution fragt er einmal über `sudo` nach dem Passwort.

Wer die Systemabhängigkeiten bereits installiert hat oder selbst verwaltet, kann sie überspringen:

```bash
./install.sh --no-system-packages
```

## Konfiguration

Die Installation erzeugt `~/.config/keydict/config.toml`. Wichtige Optionen:

- `api.url`, `api.api_key`, `api.model`: OpenAI-kompatibler Transkriptionsdienst
- `hotkey.key`: standardmäßig `F8`, alternativ beispielsweise `CTRL+ALT+D`
- `hotkey.mode`: `hold` (gedrückt halten) oder `toggle` (Start/Stopp)
- `output.mode`: `clipboard` oder `paste`
- `audio.device`: optionaler Mikrofonname oder Geräteindex

Der voreingestellte Hotkey ist `F8` im Modus `hold`. F8 kollidiert selten mit Texteingaben, ist auf nahezu allen Tastaturen vorhanden und lässt sich bei Bedarf auch in GNOME oder KDE als globaler Shortcut konfigurieren.

Um den API-Key nicht direkt in die Konfiguration zu schreiben, akzeptiert KeyDict `${OPENAI_API_KEY}`:

```bash
export OPENAI_API_KEY="…"
keydict run
```

## Manuelle Installation für Entwicklung

```bash
sudo apt install python3-venv portaudio19-dev libnotify-bin xclip xdotool wl-clipboard wtype ydotool
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/keydict init
```

## Start

```bash
keydict run
```

`hotkey.backend = "auto"` verwendet zuerst `evdev` und fällt ohne Gerätezugriff unter X11 automatisch auf einen unprivilegierten X11-Hotkey zurück. Unter Wayland wechselt KeyDict bei fehlendem Gerätezugriff in den externen Modus. Dann hinterlegt man in den globalen Tastaturkürzeln von GNOME, KDE oder der verwendeten Desktopumgebung diesen Befehl:

```bash
keydict trigger
```

Der externe Modus eignet sich besonders für `toggle`. Für `hold` muss die Desktopumgebung getrennte Befehle beim Drücken und Loslassen unterstützen: `keydict trigger press` und `keydict trigger release`.

Alternativ kann direkter Gerätezugriff freigeschaltet werden:

```bash
sudo usermod -aG input "$USER"
```

Danach ist eine erneute Anmeldung nötig. Die Gruppe `input` darf sämtliche Tastaturereignisse lesen; auf gemeinsam genutzten Systemen ist der externe Desktop-Shortcut deshalb vorzuziehen.

## Autostart mit systemd

Der Installer legt bereits `~/.config/systemd/user/keydict.service` an. Aktivieren lässt er sich mit:

```bash
systemctl --user enable --now keydict.service
```

Wenn der API-Key nur als Umgebungsvariable gesetzt ist, muss er auch für den systemd-Benutzerdienst verfügbar gemacht werden. Alternativ kann er direkt in der nur für den Benutzer lesbaren Konfigurationsdatei hinterlegt werden.
