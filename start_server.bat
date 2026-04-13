@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo [경비정산서] 서버 시작 중...
python serve.py
pause
