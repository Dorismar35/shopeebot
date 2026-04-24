@echo off
echo Parando ShopeeBot...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5020"') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo ShopeeBot parado!
timeout /t 2 >nul
