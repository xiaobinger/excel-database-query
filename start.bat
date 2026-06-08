@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   Excel Database Query - 后台启动脚本
echo ========================================
echo.

REM 检查Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
set BACKEND_DIR=%SCRIPT_DIR%backend%~nx0
set FRONTEND_DIR=%SCRIPT_DIR%frontend%~nx0

REM 启动后端
echo [1/2] 启动后端服务...
cd /d "%SCRIPT_DIR%backend"
start "Excel Query Backend" cmd /k "python run.py"
if %errorlevel% equ 0 (
    echo [成功] 后端服务已启动 (http://localhost:5000)
) else (
    echo [失败] 后端服务启动失败
)
echo.

REM 等待后端启动
timeout /t 3 /nobreak >nul

REM 启动前端
echo [2/2] 启动前端服务...
cd /d "%SCRIPT_DIR%frontend"
start "Excel Query Frontend" cmd /k "node server.js"
if %errorlevel% equ 0 (
    echo [成功] 前端服务已启动 (http://localhost:3000)
) else (
    echo [失败] 前端服务启动失败
)
echo.

echo ========================================
echo   启动完成！
echo   前端: http://localhost:3000
echo   后端: http://localhost:5000
echo ========================================
echo.
echo 提示: 关闭此窗口不会停止服务，服务在独立窗口中运行
echo 停止服务: 关闭对应的后端/前端窗口，或运行 stop.bat
echo.
pause
