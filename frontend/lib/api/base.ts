// API 基础设施：request 函数 + BASE_URL

// 默认走相对路径，由 Next.js 服务端把 /backend/* 转发到后端（见 next.config.ts）。
// 这样浏览器只需访问前端端口，后端地址不必编译进静态产物 —— 镜像才能预构建分发，
// 用户也不用再填 NAS 的 IP。
// NEXT_PUBLIC_API_URL 仍然保留：需要前端直连某个独立后端时可以覆盖。
export const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/backend";

/** 登录页路径。401 时统一跳这里，带上原地址方便登录后跳回 */
export const LOGIN_PATH = "/login";

/**
 * 会话失效时跳登录页。
 *
 * 放在 request 里而不是让每个调用点自己判断：后端一旦启用访问密码，
 * 所有接口都会 401，逐个处理必然漏。
 */
function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  if (window.location.pathname === LOGIN_PATH) return;
  const next = window.location.pathname + window.location.search;
  window.location.href = `${LOGIN_PATH}?next=${encodeURIComponent(next)}`;
}

export async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (res.status === 401) {
    // 会话过期或没登录。跳登录页后这个 promise 仍然要 reject，
    // 否则调用方会拿着 undefined 继续往下走。
    redirectToLogin();
    throw new Error("未授权，请先输入访问密码");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}
