# Napics 单镜像：前端 + 后端打包在一起
#
# 为什么合并成一个镜像：NAS 用户习惯在图形界面里「拉一个镜像、建一个容器」。
# 拆成两个容器的话，用户还得自己建自定义网络才能让它们互通，门槛太高。
#
# 容器内结构：
#   后端 FastAPI  监听 127.0.0.1:8001（不对外）
#   前端 Next.js  监听 0.0.0.0:3000（唯一对外端口），把 /backend/* 转发给后端
#
# 基础镜像选 python 官方镜像而不是 Debian 自带的 python3：
# Debian bookworm 的 python3 是 3.11，而依赖版本是在 3.13+ 上验证的。
# Python 3.12/3.14 之间类型注解的求值时机有变化（PEP 649/563），
# 版本不一致会出现 pydantic 相关的 NameError。前端只需要 node 运行时，
# 直接从官方 node 镜像复制二进制即可（standalone 产物自带 node_modules）。

# ── 阶段 1：构建前端 ──
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
# 后端地址是运行时读取的，不参与构建，所以产物对所有用户通用
RUN npm run build

# ── 阶段 2：运行镜像 ──
FROM python:3.13-slim-bookworm

# 从官方 node 镜像取运行时（两者同为 bookworm，二进制兼容）
COPY --from=node:20-bookworm-slim /usr/local/bin/node /usr/local/bin/node

# ffmpeg 提供 ffprobe 做视频分析；curl 用于健康检查
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        tzdata && \
    rm -rf /var/lib/apt/lists/*

# 注意：刻意不设 HOSTNAME。Docker 运行时会把它覆盖成容器 ID，
# 而 Next.js standalone 用它决定监听地址，所以改由 entrypoint 在启动命令上强制指定。
ENV TZ=Asia/Shanghai \
    NODE_ENV=production \
    PORT=3000 \
    NAPICS_DATA_DIR=/app/data \
    NAPICS_BACKEND_ORIGIN=http://127.0.0.1:8001 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# python 官方镜像本身就是隔离环境，不需要再套 venv
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# 构建期依赖自检：版本组合有问题时在这里就失败，并打印实际装到的版本，
# 不用等容器启动后才崩。
RUN python -c "\
import sys, fastapi, pydantic, uvicorn, starlette, requests, bs4, cloudscraper, curl_cffi; \
from pydantic import JsonValue; \
print('依赖自检通过'); \
print('  python    ', sys.version.split()[0]); \
print('  fastapi   ', fastapi.__version__); \
print('  pydantic  ', pydantic.VERSION); \
print('  starlette ', starlette.__version__)" && \
    node --version && \
    ffprobe -version | head -n 1

# 后端源码
COPY backend/ /app/backend/

# 导入自检：把「启动时才崩」的问题提前到构建阶段。
# 低版本 Python 会在导入时立即求值类型注解，注解里引用了未导入的名字就会
# NameError —— 而开发机若是 Python 3.14（注解延迟求值）则不会暴露。
RUN cd /app/backend && python -c "import main; print('后端模块导入自检通过')"

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
# URL 不带尾斜杠：/backend/ 会被 Next.js 308 重定向，curl 需要 -L 才能跟随
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsSL http://127.0.0.1:3000/backend || exit 1

CMD ["/app/entrypoint.sh"]
