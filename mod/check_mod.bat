@echo off
rem Explains why the app is or is not receiving anything from the game.
rem Usage: check_mod.bat            (finds the game itself)
rem        check_mod.bat "C:\path\to\your\Titanfall2 folder"
setlocal
set "PYEXE=%~dp0..\app\.venv\Scripts\python.exe"
if exist "%PYEXE%" (
  "%PYEXE%" "%~dp0btvoice_setup.py" check %*
) else (
  py -3 "%~dp0btvoice_setup.py" check %*
)
pause
