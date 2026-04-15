@echo off
cd /d "%~dp0"
echo ===== %date% %time% ===== >> server.log
echo CWD=%CD% >> server.log
echo USER=%USERNAME% >> server.log
where python >> server.log 2>&1
python --version >> server.log 2>&1

REM 필수 패키지 자동 확인·설치 (처음 1회만 걸림, 이후 캐시)
python -c "import flask, waitress, PIL, fitz, openpyxl, dotenv" 2>NUL
if %ERRORLEVEL% NEQ 0 (
    echo [setup] Installing missing packages... >> server.log
    python -m pip install -r requirements.txt >> server.log 2>&1
)

python serve.py >> server.log 2>&1
echo exit=%ERRORLEVEL% >> server.log
