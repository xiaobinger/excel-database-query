@echo off
chcp 65001 >nul

echo ========================================
echo   停止所有服务
echo ========================================
echo.

echo [1/2] 停止后端服务...
taskkill /FI "WINDOWTITLE eq Excel Query Backend*" /T /F >nul 2>nul
if %errorlevel% equ 0 (
    echo [成功] 后端服务已停止
) else (
    echo [提示] 后端服务未运行
)

echo [2/2] 停止前端服务...
taskkill /FI "WINDOWTITLE eq Excel Query Frontend*" /T /F >nul 2>nul
if %errorlevel% equ 0 (
    echo [成功] 前端服务已停止
) else (
    echo [提示] 前端服务未运行
)

echo.
echo ========================================
echo   所有服务已停止
echo ========================================
pause
