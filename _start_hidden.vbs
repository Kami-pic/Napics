Set WshShell = CreateObject("WScript.Shell")
Set WshEnv = WshShell.Environment("Process")
WshEnv("HIDDEN") = "1"
WshShell.Run """" & WScript.Arguments(0) & """", 0, False
