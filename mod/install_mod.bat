@echo off
rem Usage: install_mod.bat "C:\path\to\your\Titanfall2 folder"
rem Copies the BT voice sensor mod into the Titanfall 2 VR profile and allows
rem the game to talk to the app on this PC.
setlocal
set "GAME=%~1"
if "%GAME%"=="" (
  echo Usage: install_mod.bat "C:\path\to\your\Titanfall2 folder"
  exit /b 1
)
if not exist "%GAME%\Titanfall2VRLauncher.exe" (
  echo "%GAME%" does not look like the Titanfall 2 VR install: Titanfall2VRLauncher.exe is missing.
  exit /b 1
)
xcopy /E /I /Y "%~dp0TF2VR.BTVoice" "%GAME%\TF2VR\mods\TF2VR.BTVoice" >nul
if errorlevel 1 (
  echo Copy failed. If the game is under Program Files, run this as administrator.
  exit /b 1
)
set "ARGS=%GAME%\ns_startup_args.txt"
findstr /C:"-allowlocalhttp" "%ARGS%" >nul 2>nul
if errorlevel 1 echo -allowlocalhttp>>"%ARGS%"
echo Installed the mod to %GAME%\TF2VR\mods\TF2VR.BTVoice
echo Launch argument is in %ARGS%
