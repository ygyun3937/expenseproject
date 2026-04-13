@echo off
chcp 65001 > nul
setlocal
set SERVICE_NAME=ExpenseServer
set APP_DIR=%~dp0

"%APP_DIR%nssm.exe" stop %SERVICE_NAME%
"%APP_DIR%nssm.exe" remove %SERVICE_NAME% confirm
echo ✅ 서비스 제거 완료
pause
