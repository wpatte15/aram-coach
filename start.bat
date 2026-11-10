@echo off
rem Starts the coach. Pass --demo to try it without a game running.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup.bat first.
  exit /b 1
)
".venv\Scripts\python.exe" -m aramcoach %*
