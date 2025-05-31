@echo off
chcp 65001 >nul
cd /d "%~dp0"

set LOGFILE=%~dp0foreign_log.txt
echo [%date% %time%] ▶ 自動分析開始 >> %LOGFILE%

python daily_foreign_analysis.py >> %LOGFILE% 2>&1

echo [%date% %time%] ✅ 分析完成 >> %LOGFILE%
