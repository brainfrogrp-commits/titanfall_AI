@echo off
title BT Voice game mod check
rem Explains why the BT Voice app is or is not receiving anything from the game.
set "PY=%~dp0..\app\.venv\Scripts\python.exe"
if not exist "%PY%" goto no_python
"%PY%" "%~dp0btvoice_setup.py" check %*
echo.
pause
exit /b 0

:no_python
echo.
echo Start the BT Voice app once first (START_BT_VOICE.bat), so its Python is set up. Then run this again.
echo.
pause
exit /b 1
