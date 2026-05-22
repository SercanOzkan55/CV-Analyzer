@echo off
setlocal
cd /d "%~dp0"

echo CV Analyzer Local Worker
echo ========================
echo.
echo This will install/update the local worker environment and open the app.
echo No API keys are bundled in this package.
echo.

if not exist ".venv\Scripts\python.exe" (
  call "%~dp0install_windows.cmd"
  if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
) else (
  echo Existing local environment found.
)

call "%~dp0run_gui.cmd"
