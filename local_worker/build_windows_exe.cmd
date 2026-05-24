@echo off
setlocal
cd /d "%~dp0"

echo Building CV Analyzer Local Worker executable
echo ============================================

if not exist ".venv\Scripts\python.exe" (
  call "%~dp0install_windows.cmd"
)

".venv\Scripts\python.exe" -m pip install pyinstaller
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean "CV Analyzer Local Worker.spec"

echo.
echo Build complete.
echo Executable:
echo %CD%\dist\CV Analyzer Local Worker.exe
pause
