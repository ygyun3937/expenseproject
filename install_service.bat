@echo off
chcp 65001 > nul
REM Windows 서비스로 등록 (관리자 권한으로 실행 필요)
REM 사전준비: https://nssm.cc 에서 nssm.exe 다운로드 후 이 폴더에 두기

setlocal
set SERVICE_NAME=ExpenseServer
set APP_DIR=%~dp0
set PY_EXE=python
for /f "delims=" %%i in ('where python') do set PY_EXE=%%i

if not exist "%APP_DIR%nssm.exe" (
    echo [에러] nssm.exe가 없습니다. https://nssm.cc/download 에서 받아
    echo        이 폴더(%APP_DIR%)에 두세요.
    pause
    exit /b 1
)

echo [설치] 서비스 등록: %SERVICE_NAME%
"%APP_DIR%nssm.exe" install %SERVICE_NAME% "%PY_EXE%" "%APP_DIR%serve.py"
"%APP_DIR%nssm.exe" set %SERVICE_NAME% AppDirectory "%APP_DIR%"
"%APP_DIR%nssm.exe" set %SERVICE_NAME% DisplayName "경비정산서 서버"
"%APP_DIR%nssm.exe" set %SERVICE_NAME% Description "사내 경비정산 Flask 서버"
"%APP_DIR%nssm.exe" set %SERVICE_NAME% Start SERVICE_AUTO_START
"%APP_DIR%nssm.exe" set %SERVICE_NAME% AppStdout "%APP_DIR%server.log"
"%APP_DIR%nssm.exe" set %SERVICE_NAME% AppStderr "%APP_DIR%server.log"
"%APP_DIR%nssm.exe" set %SERVICE_NAME% AppRotateFiles 1
"%APP_DIR%nssm.exe" set %SERVICE_NAME% AppRotateBytes 10485760

echo [시작] 서비스 시작
"%APP_DIR%nssm.exe" start %SERVICE_NAME%

echo.
echo ✅ 완료. 서버가 백그라운드에서 실행 중입니다.
echo     로그: %APP_DIR%server.log
pause
