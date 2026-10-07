@echo off
title BT Voice game mod installer
rem Installs the BT voice game mod, then checks it, then starts the app.
set "PY=%~dp0..\app\.venv\Scripts\python.exe"
if not exist "%PY%" goto no_python
"%PY%" "%~dp0btvoice_setup.py" install %*
"%PY%" "%~dp0btvoice_setup.py" check %*
curl -s -m 2 http://127.0.0.1:5757/api/version >nul 2>nul
if not errorlevel 1 goto running
echo.
echo Starting the BT Voice app...
start "BT Voice app" "%~dp0..\START_BT_VOICE.bat"
:running
echo.
echo Close Titanfall 2 completely and start it again so it loads the mod.
echo.
pause
exit /b 0

:no_python
echo.
echo Start the BT Voice app once first (START_BT_VOICE.bat), so its Python is set up. Then run this again.
echo.
pause
exit /b 1
