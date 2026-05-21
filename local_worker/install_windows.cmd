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

echo Creating desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\CV Analyzer Local Worker.lnk'); $s.TargetPath='%CD%\run_gui.cmd'; $s.WorkingDirectory='%CD%'; $s.IconLocation='%SystemRoot%\System32\SHELL32.dll,220'; $s.Save()"

echo.
echo Setup complete.
echo Run run_gui.cmd or use the desktop shortcut to open the Local Worker app.
pause
