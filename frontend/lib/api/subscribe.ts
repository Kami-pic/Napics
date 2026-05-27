// 订阅相关 API
import { request, BASE_URL } from "./base";

export const subscribeApi = {
  getSubscriptions: (state?: string) =>
    request<any[]>(`${BASE_URL}/subscribe${state ? `?state=${state}` : ""}`),
  getSubscription: (id: string) => request<any>(`${BASE_URL}/subscribe/${id}`),
  addSubscription: (data: Record<string, any>) =>
    request<any>(`${BASE_URL}/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  updateSubscription: (id: string, data: Record<string, any>) =>
    request<any>(`${BASE_URL}/subscribe/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deleteSubscription: (id: string) =>
    request<any>(`${BASE_URL}/subscribe/${id}`, { method: "DELETE" }),
  triggerSubscriptionSearch: (id: string) =>
    request<any>(`${BASE_URL}/subscribe/${id}/search`, { method: "POST" }),
  checkSubscribed: (params: { tmdb_id?: number; title?: string; year?: string; season?: number }) => {
    const qs = new URLSearchParams();
    if (params.tmdb_id) qs.set("tmdb_id", String(params.tmdb_id));
    if (params.title) qs.set("title", params.title);
    if (params.year) qs.set("year", params.year);
    if (params.season !== undefined) qs.set("season", String(params.season));
    return request<{ subscribed: boolean }>(`${BASE_URL}/subscribe/check?${qs.toString()}`);
  },
  getSubscriptionSources: () => request<any[]>(`${BASE_URL}/subscribe/sources`),
  toggleSubscriptionSource: (name: string, enabled: boolean) =>
    request<any>(`${BASE_URL}/subscribe/sources/${name}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    }),
  getSubscriptionCalendar: () => request<any[]>(`${BASE_URL}/subscribe/calendar`),
  getSubscriptionSavePaths: () => request<{ paths: Record<string, string[]>; default: string }>(`${BASE_URL}/subscribe/save-paths`),
  // Phase 4b: 搜索日志 + 通知
  getSubscriptionLogs: (id: string) => request<any[]>(`${BASE_URL}/subscribe/${id}/logs`),
  getSubscriptionNotifications: (id: string) => request<any[]>(`${BASE_URL}/subscribe/${id}/notifications`),
  markSubscriptionNotificationsRead: (id: string) =>
    request<any>(`${BASE_URL}/subscribe/${id}/notifications/read`, { method: "POST" }),
  getUnreadNotificationCount: () => request<{ unread: number }>(`${BASE_URL}/subscribe/notifications/unread`),
};
