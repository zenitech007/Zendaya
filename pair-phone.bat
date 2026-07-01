@echo off
setlocal
title Zendaya - Pair Phone

cd /d "%~dp0"

echo(
echo ==================================================
echo   ZENDAYA - Start brain + show pairing QR
echo ==================================================
echo(

REM 1) Start Zendaya (backend + HUD) via the supervisor, if not already running.
echo [1/2] Starting Zendaya...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch-zendaya.ps1"
if errorlevel 1 (
  echo    ^(launch script reported an error - it may already be running, continuing^)
)

REM Give the server a moment to bind before we read the env / print the QR.
timeout /t 3 /nobreak >nul

echo(
echo [2/2] Pairing QR ^(scan this in the Zendaya app^):
echo --------------------------------------------------
echo(

REM 2) Print the pairing QR. Run from backend\ so package imports + .env resolve.
pushd "%~dp0backend"
"%~dp0venv\Scripts\python.exe" tools\pair_qr.py
popd

echo(
echo --------------------------------------------------
echo Open the Zendaya app on your phone, tap "Scan QR code",
echo and point it at the QR above.
echo(
echo Requirements: Tailscale connected on BOTH this PC and the phone.
echo(
pause
endlocal
