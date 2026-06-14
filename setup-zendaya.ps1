# setup-zendaya.ps1 — one-time: verify venv, install backend deps, drop desktop shortcuts.
$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot

Write-Host "[1/3] Verifying Python venv..."
$pythonw = Join-Path $repo "venv\Scripts\pythonw.exe"
$python  = Join-Path $repo "venv\Scripts\python.exe"
if (-not (Test-Path $pythonw)) {
    Write-Error "venv not found at $pythonw. Create it first:  python -m venv venv"
    exit 1
}

Write-Host "[2/3] Installing backend dependencies..."
& $python -m pip install -r (Join-Path $repo "backend\requirements.txt")
& $python -m pip install -r (Join-Path $repo "backend\requirements-offline-voice.txt")
Write-Host "    For offline TTS, also install eSpeak-NG:  winget install --id eSpeak-NG.eSpeak-NG -e"

Write-Host "[3/3] Creating desktop shortcuts..."
$desktop = [Environment]::GetFolderPath("Desktop")
$ws = New-Object -ComObject WScript.Shell

$launch = $ws.CreateShortcut((Join-Path $desktop "Zendaya.lnk"))
$launch.TargetPath = "powershell.exe"
$launch.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$(Join-Path $repo 'launch-zendaya.ps1')`""
$launch.WorkingDirectory = $repo
$launch.Save()

$quit = $ws.CreateShortcut((Join-Path $desktop "Quit Zendaya.lnk"))
$quit.TargetPath = "powershell.exe"
$quit.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$(Join-Path $repo 'quit-zendaya.ps1')`""
$quit.WorkingDirectory = $repo
$quit.Save()

Write-Host "Done. Shortcuts 'Zendaya' and 'Quit Zendaya' are on your desktop."
