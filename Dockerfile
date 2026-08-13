# Napics 单镜像：前端 + 后端打包在一起
#
# 为什么合并成一个镜像：NAS 用户习惯在图形界面里「拉一个镜像、建一个容器」。
# 拆成两个容器的话，用户还得自己建自定义网络才能让它们互通，门槛太高。
#
# 容器内结构：
#   后端 FastAPI  监听 127.0.0.1:8001（不对外）
#   前端 Next.js  监听 0.0.0.0:3000（唯一对外端口），把 /backend/* 转发给后端

# ── 阶段 1：构建前端 ──
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
# 后端地址是运行时读取的，不参与构建，所以产物对所有用户通用
RUN npm run build

# ── 阶段 2：运行镜像 ──
FROM node:20-bookworm-slim

# python3：跑后端；ffmpeg：提供 ffprobe 做视频分析；curl：健康检查与就绪探测
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        ffmpeg \
        curl \
        tzdata && \
    rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Shanghai \
    NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    NAPICS_DATA_DIR=/app/data \
    NAPICS_BACKEND_ORIGIN=http://127.0.0.1:8001 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Debian 12 起 pip 不允许直接装到系统环境（PEP 668），用 venv
COPY backend/requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt
ENV PATH="/opt/venv/bin:$PATH"

# 后端源码
COPY backend/ /app/backend/

# 前端 standalone 产物
COPY --from=frontend-builder /build/.next/standalone /app/frontend/
COPY --from=frontend-builder /build/.next/static /app/frontend/.next/static
COPY --from=frontend-builder /build/public /app/frontend/public

COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# 配置与媒体库数据；媒体目录请挂载到 /media
VOLUME ["/app/data"]

EXPOSE 3000

# 探测前端→后端的转发链路，一次覆盖两个进程
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:3000/backend/ || exit 1

CMD ["/app/entrypoint.sh"]
