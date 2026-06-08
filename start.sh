#!/bin/bash
# Excel Database Query - Linux后台启动脚本

set -e

echo "========================================"
echo "  Excel Database Query - 启动脚本"
echo "========================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python3，请先安装Python 3.8+"
    exit 1
fi

# 启动后端
echo "[1/2] 启动后端服务..."
cd "$BACKEND_DIR"
nohup python3 run.py > "$SCRIPT_DIR/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$SCRIPT_DIR/logs/backend.pid"
echo "[成功] 后端服务已启动 (PID: $BACKEND_PID, http://localhost:5000)"

# 等待后端启动
sleep 3

# 启动前端
echo "[2/2] 启动前端服务..."
cd "$FRONTEND_DIR"
nohup node server.js > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$SCRIPT_DIR/logs/frontend.pid"
echo "[成功] 前端服务已启动 (PID: $FRONTEND_PID, http://localhost:3000)"

echo ""
echo "========================================"
echo "  启动完成！"
echo "  前端: http://localhost:3000"
echo "  后端: http://localhost:5000"
echo "========================================"
echo ""
echo "日志文件: $SCRIPT_DIR/logs/"
echo "停止服务: ./stop.sh"
echo ""
