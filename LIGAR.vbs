Dim WshShell
Set WshShell = CreateObject("WScript.Shell")

Dim pasta
pasta = "C:\Users\Dorismar\Desktop\ShopeeBot"

' Mata processo anterior na porta 5020
WshShell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr :5020') do taskkill /PID %a /F", 0, True

WScript.Sleep 1000

' Inicia server.py
WshShell.Run "cmd /c cd /d """ & pasta & """ && ""C:\Python314\python.exe"" server.py >> logs\server.log 2>&1", 0, False

' Aguarda subir
WScript.Sleep 5000

' Abre navegador
WshShell.Run "cmd /c start http://localhost:5020", 0, False

Set WshShell = Nothing
