@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  call "%~dp0install_windows.cmd"
)

".venv\Scripts\python.exe" gui.py
