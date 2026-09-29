@echo off
setlocal
pushd "%~dp0\.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
set "PANCAKE_PORT=8788"

where py >nul 2>nul
if errorlevel 1 (
  start "Operation Pancake Simple Evaluator" cmd /k python -m operation_pancake.product_app --root "%CD%" --host 127.0.0.1 --port 8788
) else (
  start "Operation Pancake Simple Evaluator" cmd /k py -3 -m operation_pancake.product_app --root "%CD%" --host 127.0.0.1 --port 8788
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(30); do { try { $r=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8788/api/health' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Milliseconds 500 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
  echo.
  echo Simple Evaluator failed to start on http://127.0.0.1:8788
  echo Leave the Operation Pancake window open so its error remains visible.
  pause
  popd
  exit /b 1
)

start "" "http://127.0.0.1:8788/"
popd
exit /b 0
