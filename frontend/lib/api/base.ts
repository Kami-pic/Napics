// API 基础设施：request 函数 + BASE_URL

// 默认走相对路径，由 Next.js 服务端把 /backend/* 转发到后端（见 next.config.ts）。
// 这样浏览器只需访问前端端口，后端地址不必编译进静态产物 —— 镜像才能预构建分发，
// 用户也不用再填 NAS 的 IP。
// NEXT_PUBLIC_API_URL 仍然保留：需要前端直连某个独立后端时可以覆盖。
export const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/backend";

export async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}
