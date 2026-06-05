# setup-zendaya.ps1 — one-time: verify venv, build the HUD, drop desktop shortcuts.
$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$hud  = Join-Path $repo "zendaya-hud-react"

Write-Host "[1/4] Verifying Python venv..."
$pythonw = Join-Path $repo "venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    Write-Error "venv not found at $pythonw. Create it and install backend deps first."
    exit 1
}

Write-Host "[2/4] Building the HUD frontend..."
Push-Location $hud
npm ci
npm run build

Write-Host "[3/4] Building the Tauri desktop app (can take several minutes)..."
npm run build:app
Pop-Location

Write-Host "[4/4] Creating desktop shortcuts..."
$desktop = [Environment]::GetFolderPath("Desktop")
$icon = Join-Path $hud "src-tauri\icons\icon.ico"
$ws = New-Object -ComObject WScript.Shell

$launch = $ws.CreateShortcut((Join-Path $desktop "Zendaya.lnk"))
$launch.TargetPath = "powershell.exe"
$launch.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$(Join-Path $repo 'launch-zendaya.ps1')`""
$launch.WorkingDirectory = $repo
$launch.IconLocation = $icon
$launch.Save()

$quit = $ws.CreateShortcut((Join-Path $desktop "Quit Zendaya.lnk"))
$quit.TargetPath = "powershell.exe"
$quit.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$(Join-Path $repo 'quit-zendaya.ps1')`""
$quit.WorkingDirectory = $repo
$quit.IconLocation = $icon
$quit.Save()

Write-Host "Done. Shortcuts 'Zendaya' and 'Quit Zendaya' are on your desktop."
