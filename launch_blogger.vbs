' Heptabase -> Blogger publisher launcher
' Starts app.py hidden (no console window), then opens the browser.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir_ = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run "pyw """ & dir_ & "\app.py""", 0, False
WScript.Sleep 1500
sh.Run "http://localhost:8822", 1, False
