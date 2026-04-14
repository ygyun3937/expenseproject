@echo off
cd /d "%~dp0"
echo ===== %date% %time% ===== >> server.log
echo CWD=%CD% >> server.log
echo USER=%USERNAME% >> server.log
where python >> server.log 2>&1
python --version >> server.log 2>&1
python serve.py >> server.log 2>&1
echo exit=%ERRORLEVEL% >> server.log
