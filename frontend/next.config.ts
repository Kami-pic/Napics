import os from "node:os";
import type { NextConfig } from "next";

/**
 * 本机所有非回环 IPv4。
 *
 * 只用于 dev 的 `allowedDevOrigins`：Next 16 默认**拦掉**非 localhost 主机对
 * `/_next/*` dev 资源（含 webpack-hmr、JS chunk）的请求，于是手机上打开
 * `http://<PC-IP>:3032` 会得到一个完整的 HTML 但客户端 JS 一律加载失败 ——
 * 表现是"页面能开、内容永远停在 loading"，且看不到任何请求。
 *
 * 动态取而不是写死 IP：换机器、换网段、切有线/无线都不用改配置。
 * 这个字段在 production build 里不生效，不影响部署。
 */
function localIPv4s(): string[] {
  // 显式指定优先：`NAPICS_DEV_ORIGINS=10.1.2.3,host.local npm run dev`
  const explicit = (process.env.NAPICS_DEV_ORIGINS || "").split(",").map(s => s.trim()).filter(Boolean);
  if (explicit.length > 0) return explicit;

  return Object.values(os.networkInterfaces())
    .flat()
    .filter(info => info && info.family === "IPv4" && !info.internal)
    .map(info => info!.address)
    // 只放行 RFC1918 私网地址。os.networkInterfaces() 还会给出 Tailscale
    // （100.64/10 CGNAT）、Docker bridge、Hyper-V 这些虚拟网卡的地址，
    // 把 tailnet 的 Origin 一起放进 dev 白名单没有必要。
    .filter(addr => /^(?:192\.168\.|10\.|172\.(?:1[6-9]|2\d|3[01])\.)/.test(addr));
}

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: localIPv4s(),
  // 关闭 Next 自身的响应压缩：它会缓冲响应体，破坏扫描/搜索的实时进度推送。
  // 大 JSON 响应的压缩由后端的 gzip 中间件负责（已按路径排除 SSE）。
  compress: false,
  async headers() {
    return [
      {
        // 移动端 URL 的 query 里带媒体绝对路径，会随 Referer 一起发给外部站点
        // （详情页里的外链、网盘分享链接都会触发）。same-origin 让跨站请求只带来源域名。
        source: "/m/:path*",
        headers: [{ key: "Referrer-Policy", value: "same-origin" }],
      },
      {
        source: "/m",
        headers: [{ key: "Referrer-Policy", value: "same-origin" }],
      },
    ];
  },
};

export default nextConfig;
