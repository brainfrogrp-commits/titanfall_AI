@echo off
title Create BT Voice desktop shortcut
rem Puts a "BT Voice" shortcut on your desktop that starts the app.
set "BT_TARGET=%~dp0START_BT_VOICE.bat"
set "BT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\BT Voice.lnk'); $s.TargetPath=$env:BT_TARGET; $s.WorkingDirectory=$env:BT_DIR; $s.Description='Start the BT Voice app'; $s.Save(); Write-Host ('Created: ' + $d + '\BT Voice.lnk')"
if errorlevel 1 goto failed
echo.
echo Done. Double-click "BT Voice" on your desktop to start the app.
echo.
pause
exit /b 0

:failed
echo.
echo Could not create the shortcut. You can still double-click START_BT_VOICE.bat in this folder.
echo.
pause
exit /b 1
