$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$icon = Join-Path $root "src\\assets\\yt-dlp-gui.ico"
$ui = Join-Path $root "src\\ui"
$assets = Join-Path $root "src\\assets"

pyinstaller `
  --noconsole `
  --onefile `
  --name "yt-dlp-gui" `
  --icon $icon `
  --collect-all webview `
  --add-data "$ui;ui" `
  --add-data "$assets;assets" `
  src\\app\\main.py
