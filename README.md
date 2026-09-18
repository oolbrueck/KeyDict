# KeyDict

KeyDict ist ein konfigurierbares Diktierwerkzeug fuer Windows und Linux nach dem Push-to-talk-Prinzip. Eine globale Taste startet die Mikrofonaufnahme; nach dem Loslassen beziehungsweise dem zweiten Tastendruck wird die Aufnahme an einen OpenAI-kompatiblen Speech-to-text-Endpunkt geschickt. Das Ergebnis landet in der Zwischenablage oder direkt im aktiven Eingabefeld.

## Installation unter Windows

Voraussetzung ist [Python 3.11 oder neuer](https://www.python.org/downloads/windows/). Repository klonen und den PowerShell-Installer ausfuehren:

```powershell
git clone https://github.com/oolbrueck/KeyDict.git
cd KeyDict
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Der Installer richtet eine isolierte Umgebung unter `%LOCALAPPDATA%\KeyDict` ein, fuegt den Befehl `keydict` zum Benutzer-PATH hinzu und erzeugt `%APPDATA%\KeyDict\config.toml`. Ein neues Terminal uebernimmt den aktualisierten PATH.

Optional kann KeyDict direkt beim Anmelden gestartet werden:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -EnableStartup
```

Windows fragt beim ersten Start gegebenenfalls nach dem Mikrofonzugriff. Dieser muss in **Einstellungen > Datenschutz & Sicherheit > Mikrofon** fuer Desktop-Apps erlaubt sein.

## Installation unter Linux

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

Die Installation erzeugt unter Linux `~/.config/keydict/config.toml` und unter Windows `%APPDATA%\KeyDict\config.toml`. Wichtige Optionen:

- `api.url`, `api.api_key`, `api.model`: OpenAI-kompatibler Transkriptionsdienst
- `hotkey.key`: standardmäßig `F8`, alternativ beispielsweise `CTRL+ALT+D`
- `hotkey.mode`: `hold` (gedrückt halten) oder `toggle` (Start/Stopp)
- `output.mode`: `clipboard` oder `paste`
- `audio.device`: optionaler Mikrofonname oder Geräteindex

Der voreingestellte Hotkey ist `F8` im Modus `hold`. F8 kollidiert selten mit Texteingaben und ist auf nahezu allen Tastaturen vorhanden. Unter Windows wird der Hotkey direkt systemweit abgefangen; Administratorrechte sind nicht erforderlich.

Um den API-Key nicht direkt in die Konfiguration zu schreiben, akzeptiert KeyDict `${OPENAI_API_KEY}`:

```bash
export OPENAI_API_KEY="…"
keydict run
```

Unter Windows kann die Variable dauerhaft gesetzt werden (anschliessend ein neues Terminal oeffnen):

```powershell
[Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'sk-...', 'User')
```

## Manuelle Installation für Entwicklung

Windows (PowerShell):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\keydict init
```

Linux:

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

`hotkey.backend = "auto"` verwendet unter Windows den systemweiten `pynput`-Listener. Unter Linux wird zuerst `evdev` verwendet und ohne Gerätezugriff unter X11 automatisch auf einen unprivilegierten X11-Hotkey zurückgefallen. Unter Wayland wechselt KeyDict bei fehlendem Gerätezugriff in den externen Modus. Dann hinterlegt man in den globalen Tastaturkürzeln von GNOME, KDE oder der verwendeten Desktopumgebung diesen Befehl:

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
