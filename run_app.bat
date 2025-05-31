@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 啟動 Flask 程式...
python app.py

timeout /t 2 /nobreak >nul
start http://127.0.0.1:5000

exit
