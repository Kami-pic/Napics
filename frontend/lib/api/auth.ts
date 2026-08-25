// 访问控制 API。
// 这几个接口在后端的鉴权白名单里，未登录时也能调到。
import { request, BASE_URL } from "./base";

export interface AuthStatus {
  /** 是否设了访问密码。false 表示系统敞开，前端不显示登录页 */
  enabled: boolean;
  authenticated: boolean;
}

export const authApi = {
  getAuthStatus: () => request<AuthStatus>(`${BASE_URL}/auth/status`),

  /** 登录。密码错误时后端返回 401，这里抛错 —— 注意 request 对 401 会跳登录页，
   *  所以登录接口不能走它，否则在登录页上密码打错会触发一次自跳转。 */
  login: async (password: string): Promise<{ ok: boolean; error?: string }> => {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (res.ok) return { ok: true };
    const detail = await res.json().catch(() => null);
    return { ok: false, error: detail?.detail || `登录失败（HTTP ${res.status}）` };
  },

  logout: () => request<{ status: string }>(`${BASE_URL}/auth/logout`, { method: "POST" }),

  /** 设置 / 修改 / 关闭访问密码。newPassword 传空串表示关闭。
   *  同样不走 request：旧密码错误返回 401，不该触发跳转。 */
  setAccessPassword: async (
    newPassword: string, oldPassword = "",
  ): Promise<{ ok: boolean; enabled?: boolean; error?: string }> => {
    const res = await fetch(`${BASE_URL}/auth/password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_password: newPassword, old_password: oldPassword }),
    });
    const data = await res.json().catch(() => null);
    if (res.ok) return { ok: true, enabled: data?.enabled };
    return { ok: false, error: data?.detail || `操作失败（HTTP ${res.status}）` };
  },
};
