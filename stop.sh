#!/bin/bash
# Excel Database Query - Linux停止脚本

echo "========================================"
echo "  停止所有服务"
echo "========================================"
echo ""

# 停止后端
if [ -f "logs/backend.pid" ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    if kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID"
        echo "[成功] 后端服务已停止 (PID: $BACKEND_PID)"
    else
        echo "[提示] 后端服务未运行"
    fi
    rm -f logs/backend.pid
else
    echo "[提示] 后端服务未运行"
fi

# 停止前端
if [ -f "logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    if kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID"
        echo "[成功] 前端服务已停止 (PID: $FRONTEND_PID)"
    else
        echo "[提示] 前端服务未运行"
    fi
    rm -f logs/frontend.pid
else
    echo "[提示] 前端服务未运行"
fi

echo ""
echo "========================================"
echo "  所有服务已停止"
echo "========================================"
