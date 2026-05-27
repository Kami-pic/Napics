// 下载相关 API
import { request, BASE_URL } from "./base";

export const downloadApi = {
  download: (url: string, savePath: string, downloadType: "qb" | "alist" = "qb") => request<any>(`${BASE_URL}/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, save_path: savePath, download_type: downloadType }),
  }),

  submitDownload: (task: {
    media_name: string; download_url: string; save_path: string;
    channel?: string; category_hint?: string; is_season_pack?: boolean; season_number?: number;
    subscription_id?: string; subscription_episode?: number | null;
  }) => request<any>(`${BASE_URL}/download-manager/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(task),
  }),

  getDownloadTasks: (status?: string) =>
    request<any>(`${BASE_URL}/download-manager/tasks${status ? `?status=${status}` : ""}`),

  getDownloadProgress: () => request<any>(`${BASE_URL}/download-manager/progress`),

  syncDownloadProgress: () =>
    request<any>(`${BASE_URL}/download-manager/sync-from-qb`, { method: "POST" }),

  deleteDownloadTask: (taskId: string) =>
    request<any>(`${BASE_URL}/download-manager/task?task_id=${encodeURIComponent(taskId)}`, { method: "DELETE" }),

  deleteDownloadTasks: (taskIds: string[]) =>
    request<any>(`${BASE_URL}/download-manager/delete-tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(taskIds),
    }),

  archiveDownloadTask: (taskId: string) =>
    request<any>(`${BASE_URL}/download-manager/archive?task_id=${encodeURIComponent(taskId)}`, { method: "POST" }),

  recommendChannel: (seeders: number, sizeGb: number) =>
    request<any>(`${BASE_URL}/download-manager/recommend-channel?seeders=${seeders}&size_gb=${sizeGb}`),

  // 批量搜索升级（EventSource 流式，返回 fetch Response，不走 request）
  batchSearch: (items: { name: string; path: string; current_resolution: string }[]) =>
    fetch(`${BASE_URL}/batch-search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    }),

  // 批量下载
  batchDownload: (tasks: { download_url: string; save_path: string; download_type: "qb" | "alist" }[]) =>
    request<any>(`${BASE_URL}/batch-download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tasks }),
    }),

  // ── 归位与洗版替换 ──
  organizeDryRun: (taskId: string, autoReplace: boolean = false) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120_000); // 120 秒超时
    return request<any>(`${BASE_URL}/organize/dry-run`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId, auto_replace: autoReplace }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timeoutId));
  },
  organizeExecute: (taskId: string, plan: any) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 180_000); // 180 秒超时
    return request<any>(`${BASE_URL}/organize/execute`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId, plan }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timeoutId));
  },

  archiveBoth: (taskId: string, plan: any) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 180_000);
    return request<any>(`${BASE_URL}/organize/archive-both`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId, plan }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timeoutId));
  },

  purgeOldData: (taskId: string) =>
    request<any>(`${BASE_URL}/organize/purge-old?task_id=${encodeURIComponent(taskId)}`, { method: "POST" }),

  cancelReplace: (taskId: string) =>
    request<any>(`${BASE_URL}/download-manager/cancel-replace?task_id=${encodeURIComponent(taskId)}`, { method: "POST" }),
};
