@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  call "%~dp0install_windows.cmd"
  if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Setup failed. This window will stay open so you can read the error.
    pause
    exit /b %ERRORLEVEL%
  )
)

".venv\Scripts\python.exe" qt_gui.py
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo Local Worker closed because of an error.
  echo Crash log, if available:
  echo %LOCALAPPDATA%\CV Analyzer Local Worker\crash.log
  echo.
  pause
  exit /b %ERRORLEVEL%
)
