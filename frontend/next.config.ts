import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // 关闭 Next 自身的响应压缩：它会缓冲响应体，破坏扫描/搜索的实时进度推送。
  // 大 JSON 响应的压缩由后端的 gzip 中间件负责（已按路径排除 SSE）。
  compress: false,
};

export default nextConfig;
