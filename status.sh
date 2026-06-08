#!/bin/bash
# Excel Database Query - Linux状态查看脚本

echo "========================================"
echo "  服务状态"
echo "========================================"
echo ""

# 检查后端
if [ -f "logs/backend.pid" ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    if kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "[运行中] 后端服务 (PID: $BACKEND_PID) - http://localhost:5000"
    else
        echo "[已停止] 后端服务 (PID: $BACKEND_PID 不存在)"
    fi
else
    echo "[未启动] 后端服务"
fi

# 检查前端
if [ -f "logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    if kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo "[运行中] 前端服务 (PID: $FRONTEND_PID) - http://localhost:3000"
    else
        echo "[已停止] 前端服务 (PID: $FRONTEND_PID 不存在)"
    fi
else
    echo "[未启动] 前端服务"
fi

echo ""
echo "日志文件:"
if [ -d "logs" ]; then
    echo "  - logs/backend.log"
    echo "  - logs/frontend.log"
else
    echo "  (logs目录不存在)"
fi
echo ""
