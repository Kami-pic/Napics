import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
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
