#!/bin/bash
# 单容器启动脚本：同时拉起后端（FastAPI）与前端（Next.js）
#
# 后端只监听 127.0.0.1，不对容器外暴露 —— 浏览器的请求由前端在容器内转发。
# 这样整个应用只需要开放一个端口，后端也不会被局域网直接访问到。

set -u

BACKEND_PID=""
FRONTEND_PID=""

log() {
  echo "[entrypoint] $*"
}

shutdown() {
  log "收到停止信号，正在关闭子进程..."
  [ -n "$BACKEND_PID" ] && kill -TERM "$BACKEND_PID" 2>/dev/null || true
  [ -n "$FRONTEND_PID" ] && kill -TERM "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  log "已退出"
  exit 0
}
trap shutdown SIGTERM SIGINT

# 数据目录（挂载卷）必须存在
mkdir -p "${NAPICS_DATA_DIR:-/app/data}"

log "启动后端 (127.0.0.1:8001)..."
cd /app/backend || exit 1
python3 -m uvicorn main:app --host 127.0.0.1 --port 8001 &
BACKEND_PID=$!

# 等后端就绪再起前端，避免首屏请求打空
for i in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:8001/" >/dev/null 2>&1; then
    log "后端就绪（用时 ${i}s）"
    break
  fi
  # 后端进程已经挂了就不用再等
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "后端启动失败，容器退出"
    exit 1
  fi
  sleep 1
done

log "启动前端 (0.0.0.0:${PORT:-3000})..."
cd /app/frontend || exit 1
node server.js &
FRONTEND_PID=$!

log "启动完成，访问端口 ${PORT:-3000}"

# 任一进程退出就让容器退出，交给 Docker 的重启策略处理
wait -n
EXIT_CODE=$?
log "有子进程退出（code=$EXIT_CODE），容器即将退出"
kill -TERM "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
wait 2>/dev/null || true
exit "$EXIT_CODE"
