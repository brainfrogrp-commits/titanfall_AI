@echo off
rem Installs the BT voice game mod and turns on the launch flag it needs, then checks the result.
rem Usage: install_mod.bat            (finds the game itself)
rem        install_mod.bat "C:\path\to\your\Titanfall2 folder"
setlocal
set "PYEXE=%~dp0..\app\.venv\Scripts\python.exe"
if exist "%PYEXE%" (
  "%PYEXE%" "%~dp0btvoice_setup.py" install %*
  "%PYEXE%" "%~dp0btvoice_setup.py" check %*
) else (
  py -3 "%~dp0btvoice_setup.py" install %*
  py -3 "%~dp0btvoice_setup.py" check %*
)
pause
