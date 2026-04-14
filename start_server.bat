@echo off
cd /d "%~dp0"
echo [Expense Server] Starting...
python serve.py
pause
