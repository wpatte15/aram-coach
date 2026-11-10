@echo off
rem One-time setup: creates a private Python environment in .venv and installs what the coach needs.
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.12 or newer from https://www.python.org/downloads/ and run this again.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating the Python environment...
  py -3 -m venv .venv || exit /b 1
)

echo Installing packages...
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt || exit /b 1

if not exist ".env" (
  copy /y ".env.example" ".env" >nul
  echo Created .env. Open it and choose how the coach reaches Claude.
)

echo.
echo Setup is complete. Run start.bat to start the coach, or "start.bat --demo" to try it without a game.
