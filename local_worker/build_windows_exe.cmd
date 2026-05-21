@echo off
setlocal
cd /d "%~dp0"

echo Building CV Analyzer Local Worker executable
echo ============================================

if not exist ".venv\Scripts\python.exe" (
  call "%~dp0install_windows.cmd"
)

".venv\Scripts\python.exe" -m pip install pyinstaller
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name "CV Analyzer Local Worker" gui.py

echo.
echo Build complete.
echo Executable:
echo %CD%\dist\CV Analyzer Local Worker\CV Analyzer Local Worker.exe
pause
