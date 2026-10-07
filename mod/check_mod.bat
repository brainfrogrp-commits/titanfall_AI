@echo off
title BT Voice game mod check
setlocal

rem Explains why the BT Voice app is or is not receiving anything from the game.
rem Run it with the BT Voice app open, after starting the game and loading a level.

echo.
echo ===== BT Voice game mod check =====
echo.

set "GAME=%~1"
if defined GAME goto have_game

for %%P in ("C:\Program Files\EA Games\Titanfall2" "C:\Program Files (x86)\EA Games\Titanfall2" "C:\Program Files (x86)\Origin Games\Titanfall2" "C:\Program Files (x86)\Steam\steamapps\common\Titanfall2" "C:\Program Files\Steam\steamapps\common\Titanfall2" "D:\SteamLibrary\steamapps\common\Titanfall2" "E:\SteamLibrary\steamapps\common\Titanfall2" "D:\Games\Titanfall2" "C:\Games\Titanfall2") do if not defined GAME if exist "%%~P\Titanfall2VRLauncher.exe" set "GAME=%%~P"
if defined GAME goto have_game
for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\Respawn\Titanfall2" /v "Install Dir" 2^>nul ^| find "Install Dir"') do set "GAME=%%B"
if defined GAME if not exist "%GAME%\Titanfall2VRLauncher.exe" set "GAME="
if defined GAME goto have_game
for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\WOW6432Node\Respawn\Titanfall2" /v "Install Dir" 2^>nul ^| find "Install Dir"') do set "GAME=%%B"
if defined GAME if not exist "%GAME%\Titanfall2VRLauncher.exe" set "GAME="
if defined GAME goto have_game

echo I could not find Titanfall 2 VR by myself.
echo Type or paste the folder that contains Titanfall2VRLauncher.exe and press Enter.
echo.
set /p "GAME=Folder: "
set "GAME=%GAME:"=%"

:have_game
if not exist "%GAME%\Titanfall2VRLauncher.exe" goto not_vr
echo Game folder: %GAME%
echo.

rem ---- is the mod where the game looks for it
if exist "%GAME%\TF2VR\mods\TF2VR.BTVoice\mod.json" goto mod_ok
echo [PROBLEM] The mod is NOT installed in %GAME%\TF2VR\mods\TF2VR.BTVoice
echo           Run install_mod.bat.
goto mod_done
:mod_ok
echo [OK] The mod is installed.
:mod_done

rem ---- is the launch flag set
set "FLAGWHERE="
findstr /C:"-allowlocalhttp" "%GAME%\TF2VR\tools\launch.json" >nul 2>nul
if not errorlevel 1 set "FLAGWHERE=launch.json"
findstr /C:"-allowlocalhttp" "%GAME%\ns_startup_args.txt" >nul 2>nul
if not errorlevel 1 set "FLAGWHERE=%FLAGWHERE% ns_startup_args.txt"
if defined FLAGWHERE goto flag_ok
echo [PROBLEM] The -allowlocalhttp launch flag is not set, so the game blocks the mod from reaching the app.
echo           Run install_mod.bat. (A VR mod update can reset it, so run it again after updating.)
goto flag_done
:flag_ok
echo [OK] The -allowlocalhttp flag is set in:%FLAGWHERE%
:flag_done

rem ---- is the mod switched off
findstr /R /C:"TF2VR.BTVoice.*false" "%GAME%\TF2VR\enabledmods.json" >nul 2>nul
if errorlevel 1 goto not_off
echo [PROBLEM] The mod is switched OFF in enabledmods.json. Run install_mod.bat.
goto off_done
:not_off
echo [OK] The mod is not switched off.
:off_done

rem ---- what the game's own log says (newest log file)
set "LOG="
for /f "delims=" %%F in ('dir /b /o-d "%GAME%\TF2VR\logs\*.txt" 2^>nul') do if not defined LOG set "LOG=%GAME%\TF2VR\logs\%%F"
if defined LOG goto have_log
echo [NOTE] No game log found yet. Start the game once, load a level, then run this check again.
goto log_done
:have_log
echo Newest game log: %LOG%
findstr /C:"[BTVoice] started" "%LOG%" >nul 2>nul
if errorlevel 1 goto not_started
echo [OK] The log shows the mod loaded and started.
goto show_lines
:not_started
echo [PROBLEM] The log does NOT show the mod starting. The game did not load it: wrong folder, switched off,
echo           or a script error. Any related lines from the log are shown below.
:show_lines
echo.
echo Log lines about the mod or compile errors:
findstr /I /C:"BTVoice" /C:"bt_voice_sensors" /C:"COMPILE ERROR" "%LOG%"
echo (end of log lines)
:log_done

rem ---- has the app heard anything
echo.
curl -s -m 3 http://127.0.0.1:5757/api/status >"%TEMP%\btvoice_status.json" 2>nul
if errorlevel 1 goto app_down
findstr /C:"\"game_seconds\":null" "%TEMP%\btvoice_status.json" >nul
if not errorlevel 1 goto app_nothing
echo [OK] The app has heard from the game. It is connected.
goto app_done
:app_nothing
echo [PROBLEM] The app is running but has received nothing from the game yet.
goto app_done
:app_down
echo [NOTE] The BT Voice app is not running, so I could not ask it what it has received.
:app_done

echo.
echo Fix any [PROBLEM] lines above, restart the game completely, then run this check again.
echo If you are stuck, send everything in this window to Claude.
echo.
pause
exit /b 0

:not_vr
echo.
echo That folder does not contain Titanfall2VRLauncher.exe:
echo   %GAME%
echo.
pause
exit /b 1
