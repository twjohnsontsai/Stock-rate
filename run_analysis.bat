@echo off
chcp 65001 >nul
title 三大法人分析自動執行工具

set /p STOCK=請輸入股票代號（例如 1301）:
set /p DAYS=請輸入分析天數（例如 60）:

cd /d "C:\Users\twjoh\OneDrive\Desktop\Stock rate"
python "fetch_foreign_vs_price6.py" %STOCK% %DAYS%
pause
