# quit-zendaya.ps1 — ask the running Zendaya backend to shut down cleanly.
$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$pythonw  = Join-Path $repo "venv\Scripts\pythonw.exe"
$launcher = Join-Path $repo "backend\zendaya_launcher.py"
Start-Process -FilePath $pythonw -ArgumentList "`"$launcher`" --quit" -WorkingDirectory $repo -WindowStyle Hidden -Wait
