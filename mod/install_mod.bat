@echo off
title BT Voice game mod installer
setlocal

rem Installs the BT voice game mod into Titanfall 2 VR and turns on the launch flag it needs.
rem Just double-click it. If it cannot find the game it asks you for the folder.
rem (You can also drag the Titanfall 2 folder onto this file.)

echo.
echo ===== BT Voice game mod installer =====
echo.

set "GAME=%~1"
if defined GAME goto have_game

rem the usual places
for %%P in ("C:\Program Files\EA Games\Titanfall2" "C:\Program Files (x86)\EA Games\Titanfall2" "C:\Program Files (x86)\Origin Games\Titanfall2" "C:\Program Files (x86)\Steam\steamapps\common\Titanfall2" "C:\Program Files\Steam\steamapps\common\Titanfall2" "D:\SteamLibrary\steamapps\common\Titanfall2" "E:\SteamLibrary\steamapps\common\Titanfall2" "D:\Games\Titanfall2" "C:\Games\Titanfall2") do if not defined GAME if exist "%%~P\Titanfall2VRLauncher.exe" set "GAME=%%~P"
if defined GAME goto have_game

rem where Windows says the game is installed
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
echo Found the game: %GAME%
echo.

rem ---- 1. copy the mod
set "TARGET=%GAME%\TF2VR\mods\TF2VR.BTVoice"
xcopy /E /I /Y "%~dp0TF2VR.BTVoice" "%TARGET%" >nul
if errorlevel 1 goto copy_failed
echo [OK] Copied the mod to %TARGET%

rem ---- 2. launch flag in launch.json (the file the VR launcher reads)
set "LJ=%GAME%\TF2VR\tools\launch.json"
if not exist "%LJ%" goto no_launch_json
findstr /C:"-allowlocalhttp" "%LJ%" >nul
if not errorlevel 1 goto flag_present
copy /Y "%LJ%" "%LJ%.bak" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=$env:LJ; $q=[char]34; $t=[IO.File]::ReadAllText($p); $a=$q+'-novid'+$q; if($t.Contains($a)){ $t=$t.Replace($a,$a+', '+$q+'-allowlocalhttp'+$q); [IO.File]::WriteAllText($p,$t,(New-Object Text.UTF8Encoding $false)); exit 0 } else { exit 3 }"
if errorlevel 3 goto flag_manual
if errorlevel 1 goto flag_failed
echo [OK] Added -allowlocalhttp to launch.json (a backup is next to it as launch.json.bak)
goto flag_done
:flag_present
echo [OK] The -allowlocalhttp flag was already in launch.json
goto flag_done
:no_launch_json
echo [NOTE] launch.json was not found, so the VR mod may not be fully installed yet.
goto flag_done
:flag_manual
echo [PROBLEM] I could not safely edit launch.json. Open it in Notepad, find the line with "-novid",
echo           and add "-allowlocalhttp", right after it:  "-novid", "-allowlocalhttp",
goto flag_done
:flag_failed
echo [PROBLEM] Editing launch.json failed. Close the game and try again, or run this as administrator.
:flag_done

rem ---- 3. the same flag where Northstar also looks for extra launch arguments
set "NSA=%GAME%\ns_startup_args.txt"
findstr /C:"-allowlocalhttp" "%NSA%" >nul 2>nul
if errorlevel 1 echo -allowlocalhttp>>"%NSA%"
echo [OK] ns_startup_args.txt has the flag

rem ---- 4. make sure the profile has not switched the mod off
set "EM=%GAME%\TF2VR\enabledmods.json"
if exist "%EM%" powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=$env:EM; $t=[IO.File]::ReadAllText($p); $n=[regex]::Replace($t,'(TF2VR\.BTVoice\W+)false','${1}true'); if($n -ne $t){ [IO.File]::WriteAllText($p,$n,(New-Object Text.UTF8Encoding $false)); Write-Host '[OK] Switched the mod on in enabledmods.json' }"

echo.
echo ===== Done =====
echo Now CLOSE Titanfall 2 COMPLETELY and start it again. Mods only load when the game starts.
echo Then start the BT Voice app and look at the banner at the top of its page.
echo If it is still red, double-click check_mod.bat.
echo.
curl -s -m 2 http://127.0.0.1:5757/api/version >nul 2>nul
if not errorlevel 1 goto app_running
echo Starting the BT Voice app for you...
start "BT Voice app" "%~dp0..\START_BT_VOICE.bat"
goto finish
:app_running
echo The BT Voice app is already running.
:finish
echo.
pause
exit /b 0

:not_vr
echo.
echo That folder does not contain Titanfall2VRLauncher.exe:
echo   %GAME%
echo Install Titanfall 2 VR with CircuitLord's installer first, or give me the right folder.
echo.
pause
exit /b 1

:copy_failed
echo.
echo [PROBLEM] Windows would not let me copy into the game folder.
echo Close the game, then right-click this file and choose "Run as administrator".
echo.
pause
exit /b 1
