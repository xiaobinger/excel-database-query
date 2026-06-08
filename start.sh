#!/bin/bash
# Excel Database Query - Linux后台启动脚本（带虚拟环境管理）

set -e

echo "========================================"
echo "  Excel Database Query - 启动脚本"
echo "========================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$SCRIPT_DIR/venv"
LOGS_DIR="$SCRIPT_DIR/logs"

# 创建日志目录
mkdir -p "$LOGS_DIR"

# 检查虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo "[首次启动] 创建Python虚拟环境..."
    python3 -m venv "$VENV_DIR"
    echo "[成功] 虚拟环境已创建"
fi

# 激活虚拟环境
echo "[激活] Python虚拟环境: $VENV_DIR"
. "$VENV_DIR/bin/activate"

# 检查依赖
if [ ! -f "$VENV_DIR/.deps_installed" ]; then
    echo "[安装] 安装Python依赖..."
    cd "$BACKEND_DIR"
    pip install -r requirements.txt
    touch "$VENV_DIR/.deps_installed"
    echo "[成功] Python依赖已安装"
fi

# 检查Node依赖
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "[安装] 安装Node依赖..."
    cd "$FRONTEND_DIR"
    npm install
    echo "[成功] Node依赖已安装"
fi

# 启动后端
echo ""
echo "[启动] 后端服务..."
cd "$BACKEND_DIR"
nohup python3 run.py > "$LOGS_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$LOGS_DIR/backend.pid"
echo "[成功] 后端服务已启动 (PID: $BACKEND_PID, http://localhost:5000)"

# 等待后端启动
sleep 3

# 启动前端
echo "[启动] 前端服务..."
cd "$FRONTEND_DIR"
nohup npm run dev > "$LOGS_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$LOGS_DIR/frontend.pid"
echo "[成功] 前端服务已启动 (PID: $FRONTEND_PID, http://localhost:3000)"

echo ""
echo "========================================"
echo "  启动完成！"
echo "  前端: http://localhost:3000"
echo "  后端: http://localhost:5000"
echo "========================================"
echo ""
echo "日志文件: $LOGS_DIR/"
echo "停止服务: ./stop.sh"
echo ""
