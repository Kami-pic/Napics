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

log "环境自检: python=$(python3 --version 2>&1) node=$(node --version 2>&1)"
log "数据目录=${NAPICS_DATA_DIR:-/app/data} 后端地址=${NAPICS_BACKEND_ORIGIN:-未设置}"

log "启动后端 (127.0.0.1:8001)..."
cd /app/backend || exit 1
python3 -m uvicorn main:app --host 127.0.0.1 --port 8001 &
BACKEND_PID=$!

# 等后端就绪再起前端，避免首屏请求打空
BACKEND_READY=0
for i in $(seq 1 90); do
  if curl -fsS "http://127.0.0.1:8001/" >/dev/null 2>&1; then
    log "后端就绪（用时 ${i}s）"
    BACKEND_READY=1
    break
  fi
  # 后端进程已经挂了就不用再等
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "后端进程已退出，启动失败。上面的 traceback 就是原因。"
    exit 1
  fi
  if [ $((i % 15)) -eq 0 ]; then
    log "等待后端就绪... ${i}s"
  fi
  sleep 1
done

if [ "$BACKEND_READY" -ne 1 ]; then
  log "后端 90 秒仍未响应 /，放弃启动"
  kill -TERM "$BACKEND_PID" 2>/dev/null || true
  exit 1
fi

# Docker 会把 HOSTNAME 环境变量设成容器 ID，而 Next.js standalone 用
# process.env.HOSTNAME 决定监听地址 —— 不显式覆盖的话会绑到容器 ID 上，
# 导致端口映射进来的请求访问不到。这里用 env 强制指定。
# 默认值必须和 Dockerfile 的 ENV PORT 一致。曾经这里兜底写 3000、
# Dockerfile 写 3032，CI 的 smoke test 照着 3000 映射端口，结果每次都连不上。
log "启动前端 (0.0.0.0:${PORT:-3032})..."
cd /app/frontend || exit 1
env HOSTNAME=0.0.0.0 PORT="${PORT:-3032}" node server.js &
FRONTEND_PID=$!

# 确认前端真的在监听，否则早点报错而不是让外部干等
FRONTEND_READY=0
for i in $(seq 1 60); do
  if curl -fsS -o /dev/null "http://127.0.0.1:${PORT:-3032}/" 2>/dev/null; then
    log "前端就绪（用时 ${i}s）"
    FRONTEND_READY=1
    break
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    log "前端进程已退出，启动失败"
    kill -TERM "$BACKEND_PID" 2>/dev/null || true
    exit 1
  fi
  sleep 1
done

if [ "$FRONTEND_READY" -ne 1 ]; then
  log "前端 60 秒仍未响应，放弃启动"
  kill -TERM "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  exit 1
fi

# 容器 DNS 自检：部分 NAS 的 Docker 默认网络拿不到可用 DNS，
# 表现为容器内所有域名解析失败，刮削 / 搜索 / 发现页 / 插件源全部不可用。
# 在这里提前报警，避免用户逐个功能试错才发现是网络问题。
if python3 -c "import socket; socket.getaddrinfo('api.themoviedb.org', 443)" >/dev/null 2>&1; then
  log "网络自检: 域名解析正常"
else
  log "============================================================"
  log "警告: 容器内域名解析失败（DNS 不可用）"
  log "刮削、搜索、发现页、插件源都将无法工作。"
  log "解决办法：为容器显式指定 DNS，例如 223.5.5.5 / 119.29.29.29"
  log "  docker run 时加: --dns 223.5.5.5 --dns 119.29.29.29"
  log "  compose 里加:   dns: [223.5.5.5, 119.29.29.29]"
  log "  NAS 图形界面：在容器的网络设置里填写 DNS"
  log "============================================================"
fi

log "启动完成，访问端口 ${PORT:-3032}"

# 任一进程退出就让容器退出，交给 Docker 的重启策略处理
wait -n
EXIT_CODE=$?
log "有子进程退出（code=$EXIT_CODE），容器即将退出"
kill -TERM "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
wait 2>/dev/null || true
exit "$EXIT_CODE"
