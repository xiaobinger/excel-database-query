# Excel Database Query - Windows 重启脚本（拉取代码并按需重启对应服务）
#
# 用法: .\restart.ps1
#
# 逻辑:
#   1. 从 git 远程仓库拉取最新代码
#   2. 对比拉取前后的代码变更:
#      - 仅前端变更   -> 只重启前端服务
#      - 仅后端变更   -> 只重启后端服务
#      - 前后端均变更 -> 重启前后端服务
#      - 无变更       -> 不做任何操作

$ErrorActionPreference = "Stop"

Write-Host "========================================"
Write-Host "  Excel Database Query - 重启脚本 (Windows)"
Write-Host "========================================"
Write-Host ""

$ScriptDir = $PSScriptRoot
$BackendDir = Join-Path $ScriptDir "backend"
$FrontendDir = Join-Path $ScriptDir "frontend"
$VenvDir = Join-Path $ScriptDir "venv"
$LogsDir = Join-Path $ScriptDir "logs"

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}

# ── 服务控制函数 ─────────────────────────────────────────

function Stop-Backend {
    Write-Host "[停止] 后端服务..."
    $pidFile = Join-Path $LogsDir "backend.pid"
    if (Test-Path $pidFile) {
        $procId = [int](Get-Content $pidFile -Raw).Trim()
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            # 优先尝试优雅停止（taskkill 发送 Ctrl+C 信号）
            taskkill /PID $procId /T 2>$null | Out-Null
            # 等待进程退出（最多 5 秒）
            for ($i = 1; $i -le 10; $i++) {
                $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if (-not $proc) { break }
                Start-Sleep -Milliseconds 500
            }
            # 仍未退出则强制杀
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc) {
                taskkill /PID $procId /T /F 2>$null | Out-Null
            }
            Write-Host "[成功] 后端服务已停止 (PID: $procId)"
        } else {
            Write-Host "[提示] 后端服务未运行"
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "[提示] 后端服务未运行"
    }
}

function Stop-Frontend {
    Write-Host "[停止] 前端服务..."
    $pidFile = Join-Path $LogsDir "frontend.pid"
    if (Test-Path $pidFile) {
        $procId = [int](Get-Content $pidFile -Raw).Trim()
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            taskkill /PID $procId /T 2>$null | Out-Null
            for ($i = 1; $i -le 10; $i++) {
                $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if (-not $proc) { break }
                Start-Sleep -Milliseconds 500
            }
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc) {
                taskkill /PID $procId /T /F 2>$null | Out-Null
            }
            Write-Host "[成功] 前端服务已停止 (PID: $procId)"
        } else {
            Write-Host "[提示] 前端服务未运行"
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "[提示] 前端服务未运行"
    }
}

function Start-Backend {
    Write-Host "[启动] 后端服务..."
    # 激活 venv（若存在）
    $pythonExe = "python"
    if (Test-Path $VenvDir) {
        $venvPython = Join-Path $VenvDir "Scripts\python.exe"
        if (Test-Path $venvPython) {
            $pythonExe = $venvPython
        }
    }
    $logFile = Join-Path $LogsDir "backend.log"
    $proc = Start-Process -FilePath $pythonExe -ArgumentList "run.py" -WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput $logFile -RedirectStandardError $logFile
    $proc.Id | Out-File -FilePath (Join-Path $LogsDir "backend.pid") -Encoding ASCII
    Write-Host "[成功] 后端服务已启动 (PID: $($proc.Id), http://localhost:5000)"
}

function Start-Frontend {
    Write-Host "[启动] 前端服务..."
    $logFile = Join-Path $LogsDir "frontend.log"
    $proc = Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WorkingDirectory $FrontendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput $logFile -RedirectStandardError $logFile
    $proc.Id | Out-File -FilePath (Join-Path $LogsDir "frontend.pid") -Encoding ASCII
    Write-Host "[成功] 前端服务已启动 (PID: $($proc.Id), http://localhost:3000)"
}

# ── 1. 拉取代码 ──────────────────────────────────────────

Write-Host "[拉取] 从远程仓库获取最新代码..."
Set-Location $ScriptDir
$oldHead = git rev-parse HEAD
git pull
$newHead = git rev-parse HEAD
Write-Host ""

if ($oldHead -eq $newHead) {
    Write-Host "[提示] 远程仓库无新代码更新，无需重启"
    Write-Host ""
    exit 0
}

$oldShort = $oldHead.Substring(0, 7)
$newShort = $newHead.Substring(0, 7)
Write-Host "[更新] 代码已更新: $oldShort -> $newShort"

# ── 2. 判断变更范围 ──────────────────────────────────────

$changedFiles = git diff --name-only $oldHead $newHead

$frontendChanged = $false
$backendChanged = $false

foreach ($file in $changedFiles) {
    if ($file -match "^frontend/") { $frontendChanged = $true }
    if ($file -match "^backend/")  { $backendChanged = $true }
}

$feText = if ($frontendChanged) { "是" } else { "否" }
$beText = if ($backendChanged) { "是" } else { "否" }
Write-Host "[变更] 前端代码: $feText | 后端代码: $beText"
Write-Host ""

if (-not $frontendChanged -and -not $backendChanged) {
    Write-Host "[提示] 变更不涉及前后端服务代码，无需重启"
    Write-Host ""
    exit 0
}

# ── 3. 依赖更新（如涉及）──────────────────────────────────

if ($backendChanged -and ($changedFiles -contains "backend/requirements.txt")) {
    Write-Host "[依赖] 检测到 requirements.txt 变更，重新安装后端依赖..."
    $pythonExe = "python"
    if (Test-Path $VenvDir) {
        $venvPip = Join-Path $VenvDir "Scripts\pip.exe"
        if (Test-Path $venvPip) {
            $pythonExe = $venvPip
        }
    }
    Set-Location $BackendDir
    & $pythonExe install -r requirements.txt
    Write-Host "[成功] 后端依赖已更新"
    Write-Host ""
}

if ($frontendChanged -and ($changedFiles -contains "frontend/package.json")) {
    Write-Host "[依赖] 检测到 package.json 变更，重新安装前端依赖..."
    Set-Location $FrontendDir
    npm install
    Write-Host "[成功] 前端依赖已更新"
    Write-Host ""
}

# ── 4. 重启对应服务 ──────────────────────────────────────

if ($frontendChanged) { Stop-Frontend }
if ($backendChanged)  { Stop-Backend }

Write-Host ""

# 等待端口释放
Start-Sleep -Seconds 2

if ($backendChanged) {
    Start-Backend
    Start-Sleep -Seconds 3
}

if ($frontendChanged) {
    Start-Frontend
}

Write-Host ""
Write-Host "========================================"
Write-Host "  重启完成！"
if ($backendChanged)  { Write-Host "  后端: http://localhost:5000" }
if ($frontendChanged) { Write-Host "  前端: http://localhost:3000" }
Write-Host "  日志: $LogsDir\"
Write-Host "  状态: .\status.ps1"
Write-Host "========================================"
Write-Host ""
