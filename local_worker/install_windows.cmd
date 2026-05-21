@echo off
setlocal
cd /d "%~dp0"

echo CV Analyzer Local Worker setup
echo ==============================

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set "PYTHON=py -3"
) else (
  where python >nul 2>nul
  if %ERRORLEVEL% NEQ 0 (
    echo Python 3 is required. Install Python from https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
  set "PYTHON=python"
)

if not exist ".venv" (
  echo Creating virtual environment...
  %PYTHON% -m venv .venv
)

echo Installing worker dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo.
echo Setup complete.
echo Run run_gui.cmd to open the Local Worker app.
pause
