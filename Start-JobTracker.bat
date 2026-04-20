@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-JobTracker.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo JobTracker exited with code %EXIT_CODE%.
)

echo.
echo Press any key to close this window.
pause >nul
exit /b %EXIT_CODE%
