[CmdletBinding()]
param(
    [switch]$EnableStartup
)

$ErrorActionPreference = 'Stop'
$SourceDir = $PSScriptRoot
$InstallRoot = Join-Path $env:LOCALAPPDATA 'KeyDict'
$VenvDir = Join-Path $InstallRoot 'venv'
$BinDir = Join-Path $InstallRoot 'bin'
$ConfigFile = Join-Path $env:APPDATA 'KeyDict\config.toml'

$Launcher = Get-Command py -ErrorAction SilentlyContinue
$LauncherArgs = @('-3')
if (-not $Launcher) {
    $Launcher = Get-Command python -ErrorAction SilentlyContinue
    $LauncherArgs = @()
}
if (-not $Launcher) {
    throw 'Python 3.11 oder neuer wurde nicht gefunden. Installiere Python zuerst von https://www.python.org/downloads/windows/'
}

$VersionOutput = & $Launcher.Source @LauncherArgs --version
if ($VersionOutput -notmatch '(\d+\.\d+(?:\.\d+)?)') {
    throw "Python-Version konnte nicht ermittelt werden: $VersionOutput"
}
$Version = [version]$Matches[1]
if ($Version -lt [version]'3.11') {
    throw "Python 3.11 oder neuer ist erforderlich; gefunden wurde $Version."
}

Write-Host "Installiere KeyDict nach $InstallRoot ..."
New-Item -ItemType Directory -Force -Path $InstallRoot, $BinDir | Out-Null
& $Launcher.Source @LauncherArgs -m venv $VenvDir
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install --upgrade $SourceDir

$Wrapper = Join-Path $BinDir 'keydict.cmd'
$WrapperContent = "@echo off`r`n`"$VenvPython`" -m keydict %*`r`n"
Set-Content -LiteralPath $Wrapper -Value $WrapperContent -Encoding Ascii -NoNewline

$UserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$PathParts = @($UserPath -split ';' | Where-Object { $_ })
if ($BinDir -notin $PathParts) {
    $NewUserPath = (@($PathParts) + $BinDir) -join ';'
    [Environment]::SetEnvironmentVariable('Path', $NewUserPath, 'User')
    Write-Host "Zum Benutzer-PATH hinzugefuegt: $BinDir"
}
$env:Path = "$BinDir;$env:Path"

if (-not (Test-Path -LiteralPath $ConfigFile)) {
    & $VenvPython -m keydict init
} else {
    Write-Host "Bestehende Konfiguration bleibt unveraendert: $ConfigFile"
}

if ($EnableStartup) {
    $StartupDir = [Environment]::GetFolderPath('Startup')
    $ShortcutPath = Join-Path $StartupDir 'KeyDict.lnk'
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = Join-Path $VenvDir 'Scripts\pythonw.exe'
    $Shortcut.Arguments = '-m keydict run'
    $Shortcut.WorkingDirectory = $InstallRoot
    $Shortcut.Description = 'KeyDict Sprachdiktion'
    $Shortcut.Save()
    Write-Host "Autostart aktiviert: $ShortcutPath"
}

Write-Host ''
Write-Host 'KeyDict wurde installiert.'
Write-Host "1. Bearbeite: $ConfigFile"
Write-Host '2. Trage dort den API-Key ein oder setze OPENAI_API_KEY dauerhaft.'
Write-Host '3. Starte ein neues Terminal und fuehre aus: keydict run'
if (-not $EnableStartup) {
    Write-Host 'Optionaler Autostart: .\install.ps1 -EnableStartup'
}
