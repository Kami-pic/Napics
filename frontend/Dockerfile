FROM node:20-alpine AS builder

WORKDIR /app

# 不再有构建期的 API 地址注入：前端走相对路径 /backend/*，
# 由 Next.js 服务端按运行时环境变量 NAPICS_BACKEND_ORIGIN 转发。
# 这样同一个镜像可以给所有用户用。

# 安装依赖
COPY package.json package-lock.json* ./
RUN npm ci

# 复制源码并构建
COPY . .
RUN npm run build

# --- 运行阶段 ---
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
# 默认指向 compose 里的后端服务名，可被 compose/环境变量覆盖
ENV NAPICS_BACKEND_ORIGIN=http://backend:8001

# 复制 standalone 构建产物
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
