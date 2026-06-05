# launch-zendaya.ps1 — start Zendaya (backend hidden + HUD) via the supervisor.
$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$pythonw  = Join-Path $repo "venv\Scripts\pythonw.exe"
$launcher = Join-Path $repo "backend\zendaya_launcher.py"
Start-Process -FilePath $pythonw -ArgumentList "`"$launcher`"" -WorkingDirectory $repo -WindowStyle Hidden
