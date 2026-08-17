# Excel Database Query - Windows 状态查看脚本

Write-Host "========================================"
Write-Host "  服务状态"
Write-Host "========================================"
Write-Host ""

$LogsDir = Join-Path $PSScriptRoot "logs"

# 检查后端
$backendPidFile = Join-Path $LogsDir "backend.pid"
if (Test-Path $backendPidFile) {
    $backendPid = [int](Get-Content $backendPidFile -Raw).Trim()
    $proc = Get-Process -Id $backendPid -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "[运行中] 后端服务 (PID: $backendPid) - http://localhost:5000"
    } else {
        Write-Host "[已停止] 后端服务 (PID: $backendPid 不存在)"
    }
} else {
    Write-Host "[未启动] 后端服务"
}

# 检查前端
$frontendPidFile = Join-Path $LogsDir "frontend.pid"
if (Test-Path $frontendPidFile) {
    $frontendPid = [int](Get-Content $frontendPidFile -Raw).Trim()
    $proc = Get-Process -Id $frontendPid -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "[运行中] 前端服务 (PID: $frontendPid) - http://localhost:3000"
    } else {
        Write-Host "[已停止] 前端服务 (PID: $frontendPid 不存在)"
    }
} else {
    Write-Host "[未启动] 前端服务"
}

Write-Host ""
Write-Host "日志文件:"
if (Test-Path $LogsDir) {
    Write-Host "  - logs\backend.log"
    Write-Host "  - logs\frontend.log"
} else {
    Write-Host "  (logs 目录不存在)"
}
Write-Host ""
