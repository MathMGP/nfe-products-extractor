' Inicia o app na bandeja sem janela de console.
Set sh = CreateObject("WScript.Shell")
appDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
sh.CurrentDirectory = appDir
sh.Run "pythonw.exe """ & appDir & "app.py""", 0, False
