// 后端 API 流式代理
//
// 路由用可选 catch-all（双方括号）而不是 [...path]：
// 单方括号不匹配空路径段，导致 /backend 本身（对应后端根接口 GET /）转发不到。
// 双方括号能同时匹配 /backend 与 /backend/任意路径。
//
// 为什么不用 next.config 的 rewrites：rewrites 会把响应整个缓冲下来再返回，
// 实测扫描接口的 10 个进度事件全部在同一时刻到达（等扫描完才一起吐出来），
// 进度条会完全不动。这里手动透传上游的 ReadableStream，保证 SSE 实时推送。
//
// 好处：浏览器只访问前端端口，后端不必暴露到宿主机；后端地址是运行时读取的
// 环境变量，不编译进前端产物，所以镜像可以预构建给所有用户通用。
import type { NextRequest } from "next/server";

const BACKEND_ORIGIN = process.env.NAPICS_BACKEND_ORIGIN || "http://127.0.0.1:8001";

// 禁止任何缓存与静态优化，必须每次真实转发
export const dynamic = "force-dynamic";
export const revalidate = 0;

// 逐跳首部：不能原样转发给上游或回传给浏览器
const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
]);

function buildUpstreamHeaders(req: NextRequest): Headers {
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  // 让上游不要压缩：压缩会引入缓冲，破坏 SSE 的实时性
  headers.set("accept-encoding", "identity");
  return headers;
}

function buildClientHeaders(upstream: Response): Headers {
  const headers = new Headers();
  upstream.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    // content-length / content-encoding 在流式透传下不再准确
    if (HOP_BY_HOP.has(lower) || lower === "content-length" || lower === "content-encoding") {
      return;
    }
    headers.set(key, value);
  });
  // 明确关闭中间层缓冲（部分反向代理会读这个头）
  if ((headers.get("content-type") || "").includes("text/event-stream")) {
    headers.set("cache-control", "no-cache, no-transform");
    headers.set("x-accel-buffering", "no");
  }
  return headers;
}

async function proxy(req: NextRequest, pathSegments: string[]): Promise<Response> {
  const search = new URL(req.url).search;
  const target = `${BACKEND_ORIGIN}/${pathSegments.join("/")}${search}`;

  const init: RequestInit & { duplex?: "half" } = {
    method: req.method,
    headers: buildUpstreamHeaders(req),
    redirect: "manual",
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req.body;
    // Node 的 fetch 用流做请求体时必须声明 duplex
    init.duplex = "half";
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch (e) {
    return new Response(
      JSON.stringify({ detail: `无法连接后端服务: ${(e as Error).message}` }),
      { status: 502, headers: { "content-type": "application/json" } },
    );
  }

  // 直接透传上游流，不做任何聚合
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: buildClientHeaders(upstream),
  });
}

// 可选 catch-all 在访问 /backend 时 path 为 undefined
type Ctx = { params: Promise<{ path?: string[] }> };

async function handle(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path ?? []);
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
export const HEAD = handle;
export const OPTIONS = handle;
