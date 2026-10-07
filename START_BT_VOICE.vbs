' Double-click to run the BT Voice app. This opens the same window as the .bat file, but starts it through Windows Script Host.
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
target = here & "\START_BT_VOICE.bat"
If Not fso.FileExists(target) Then
  MsgBox "Could not find " & target & vbCrLf & "Run git pull in the titanfall_AI folder, then try again.", vbExclamation, "BT Voice"
Else
  q = Chr(34)
  shell.CurrentDirectory = here
  shell.Run "cmd /c " & q & q & target & q & q, 1, False
End If
