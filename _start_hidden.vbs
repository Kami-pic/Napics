' 无窗口运行 bat 脚本的辅助 VBS
' 用法: cscript //nologo _start_hidden.vbs "path\to\script.bat" [args...]
Set WshShell = CreateObject("WScript.Shell")
cmd = ""
For i = 0 To WScript.Arguments.Count - 1
    If i = 0 Then
        cmd = """" & WScript.Arguments(i) & """"
    Else
        cmd = cmd & " " & WScript.Arguments(i)
    End If
Next
WshShell.Run cmd, 0, False
