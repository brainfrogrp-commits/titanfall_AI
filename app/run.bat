@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if not errorlevel 1 ( py -3 -m venv .venv ) else ( python -m venv .venv )
)
if not exist ".venv\Scripts\python.exe" (
  echo Could not create the Python environment.
  echo Install Python 3.10 or newer from python.org and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

rem Runs every launch so an interrupted install repairs itself; quick when nothing is missing.
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo.
  echo Installing the dependencies failed. Copy the error above and send it to Claude.
  pause
  exit /b 1
)

start "" http://127.0.0.1:5757
".venv\Scripts\python.exe" server.py
rem a normal exit (for example after "goodbye BT") closes this window; only an error keeps it open
if errorlevel 1 pause
