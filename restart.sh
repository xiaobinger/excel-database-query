#!/bin/bash
# Excel Database Query - 重启脚本（拉取代码并按需重启对应服务）
#
# 用法: ./restart.sh
#
# 逻辑:
#   1. 从 git 远程仓库拉取最新代码
#   2. 对比拉取前后的代码变更:
#      - 仅前端变更   -> 只重启前端服务
#      - 仅后端变更   -> 只重启后端服务
#      - 前后端均变更 -> 重启前后端服务
#      - 无变更       -> 不做任何操作

set -e

echo "========================================"
echo "  Excel Database Query - 重启脚本"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$SCRIPT_DIR/venv"
LOGS_DIR="$SCRIPT_DIR/logs"

mkdir -p "$LOGS_DIR"

# ── 服务控制函数 ─────────────────────────────────────────

stop_backend() {
    echo "[停止] 后端服务..."
    if [ -f "$LOGS_DIR/backend.pid" ]; then
        local PID=$(cat "$LOGS_DIR/backend.pid")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            # 等待进程退出（最多 5 秒）
            for i in $(seq 1 10); do
                kill -0 "$PID" 2>/dev/null || break
                sleep 0.5
            done
            # 仍未退出则强制杀
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID" 2>/dev/null || true
            fi
            echo "[成功] 后端服务已停止 (PID: $PID)"
        else
            echo "[提示] 后端服务未运行"
        fi
        rm -f "$LOGS_DIR/backend.pid"
    else
        echo "[提示] 后端服务未运行"
    fi
}

stop_frontend() {
    echo "[停止] 前端服务..."
    if [ -f "$LOGS_DIR/frontend.pid" ]; then
        local PID=$(cat "$LOGS_DIR/frontend.pid")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            for i in $(seq 1 10); do
                kill -0 "$PID" 2>/dev/null || break
                sleep 0.5
            done
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID" 2>/dev/null || true
            fi
            echo "[成功] 前端服务已停止 (PID: $PID)"
        else
            echo "[提示] 前端服务未运行"
        fi
        rm -f "$LOGS_DIR/frontend.pid"
    else
        echo "[提示] 前端服务未运行"
    fi
}

start_backend() {
    echo "[启动] 后端服务..."
    if [ -d "$VENV_DIR" ]; then
        . "$VENV_DIR/bin/activate"
    fi
    cd "$BACKEND_DIR"
    nohup python3 run.py > "$LOGS_DIR/backend.log" 2>&1 &
    local PID=$!
    echo "$PID" > "$LOGS_DIR/backend.pid"
    echo "[成功] 后端服务已启动 (PID: $PID, http://localhost:5000)"
}

start_frontend() {
    echo "[启动] 前端服务..."
    cd "$FRONTEND_DIR"
    nohup npm run dev > "$LOGS_DIR/frontend.log" 2>&1 &
    local PID=$!
    echo "$PID" > "$LOGS_DIR/frontend.pid"
    echo "[成功] 前端服务已启动 (PID: $PID, http://localhost:3000)"
}

# ── 1. 拉取代码 ──────────────────────────────────────────

echo "[拉取] 从远程仓库获取最新代码..."
cd "$SCRIPT_DIR"
OLD_HEAD=$(git rev-parse HEAD)
git pull
NEW_HEAD=$(git rev-parse HEAD)
echo ""

if [ "$OLD_HEAD" = "$NEW_HEAD" ]; then
    echo "[提示] 远程仓库无新代码更新，无需重启"
    echo ""
    exit 0
fi

OLD_SHORT=$(echo "$OLD_HEAD" | cut -c1-7)
NEW_SHORT=$(echo "$NEW_HEAD" | cut -c1-7)
echo "[更新] 代码已更新: $OLD_SHORT -> $NEW_SHORT"

# ── 2. 判断变更范围 ──────────────────────────────────────

CHANGED_FILES=$(git diff --name-only "$OLD_HEAD" "$NEW_HEAD")

FRONTEND_CHANGED=0
BACKEND_CHANGED=0

if echo "$CHANGED_FILES" | grep -q "^frontend/"; then
    FRONTEND_CHANGED=1
fi
if echo "$CHANGED_FILES" | grep -q "^backend/"; then
    BACKEND_CHANGED=1
fi

echo "[变更] 前端代码: $([ $FRONTEND_CHANGED -eq 1 ] && echo '是' || echo '否') | 后端代码: $([ $BACKEND_CHANGED -eq 1 ] && echo '是' || echo '否')"
echo ""

if [ $FRONTEND_CHANGED -eq 0 ] && [ $BACKEND_CHANGED -eq 0 ]; then
    echo "[提示] 变更不涉及前后端服务代码，无需重启"
    echo ""
    exit 0
fi

# ── 3. 依赖更新（如涉及）──────────────────────────────────

if [ $BACKEND_CHANGED -eq 1 ] && echo "$CHANGED_FILES" | grep -q "^backend/requirements.txt$"; then
    echo "[依赖] 检测到 requirements.txt 变更，重新安装后端依赖..."
    if [ -d "$VENV_DIR" ]; then
        . "$VENV_DIR/bin/activate"
    fi
    cd "$BACKEND_DIR"
    pip install -r requirements.txt
    echo "[成功] 后端依赖已更新"
    echo ""
fi

if [ $FRONTEND_CHANGED -eq 1 ] && echo "$CHANGED_FILES" | grep -q "^frontend/package.json$"; then
    echo "[依赖] 检测到 package.json 变更，重新安装前端依赖..."
    cd "$FRONTEND_DIR"
    npm install
    echo "[成功] 前端依赖已更新"
    echo ""
fi

# ── 4. 重启对应服务 ──────────────────────────────────────

if [ $FRONTEND_CHANGED -eq 1 ]; then
    stop_frontend
fi

if [ $BACKEND_CHANGED -eq 1 ]; then
    stop_backend
fi

echo ""

# 等待端口释放
sleep 2

if [ $BACKEND_CHANGED -eq 1 ]; then
    start_backend
    sleep 3
fi

if [ $FRONTEND_CHANGED -eq 1 ]; then
    start_frontend
fi

echo ""
echo "========================================"
echo "  重启完成！"
[ $BACKEND_CHANGED -eq 1 ]  && echo "  后端: http://localhost:5000"
[ $FRONTEND_CHANGED -eq 1 ] && echo "  前端: http://localhost:3000"
echo "  日志: $LOGS_DIR/"
echo "  状态: ./status.sh"
echo "========================================"
echo ""
