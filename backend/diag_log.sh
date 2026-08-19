#!/bin/bash
# 诊断：提取后端日志中AI请求相关内容
cd /usr/local/xiongbing/excel-database-query
LOG=logs/backend.log
if [ ! -f "$LOG" ]; then
  # 找实际日志位置
  find . -name "*.log" -mmin -600 2>/dev/null | head -5
  ls -la logs/ 2>/dev/null
  exit 0
fi
echo "== 日志文件: $LOG ($(wc -l < $LOG) 行) =="
# 提取今天14:30之后的日志
grep -n "14:3[0-9]\|14:4[0-9]" "$LOG" | grep -i "ai\|chat\|tool\|流式\|空\|重试\|attempt" | tail -80
