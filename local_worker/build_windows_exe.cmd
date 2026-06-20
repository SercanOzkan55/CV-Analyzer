@echo off
setlocal
cd /d "%~dp0"

echo Building CV Analyzer Local Worker executable
echo ============================================

if not exist ".venv\Scripts\python.exe" (
  call "%~dp0install_windows.cmd"
)

REM pip upgrade disabled for build reproducibility
REM ".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean "CV Analyzer Local Worker.spec"

echo.
echo Build complete.
echo Executable:
echo %CD%\dist\CV Analyzer Local Worker.exe
pause
