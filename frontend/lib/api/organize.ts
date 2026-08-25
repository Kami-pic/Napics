// 整理相关 API
import { request, BASE_URL } from "./base";

export const organizeApi = {
  classify: (path: string) => request<any>(`${BASE_URL}/organize/classify?path=${encodeURIComponent(path)}`),
  analyzeFolder: (path: string, enhanced: boolean = false) => request<any>(`${BASE_URL}/analyze/folder?path=${encodeURIComponent(path)}&enhanced=${enhanced}`),
  analyzeLibrary: (enhanced: boolean = false) => request<any>(`${BASE_URL}/analyze/library?enhanced=${enhanced}`),
  renameVideos: (path: string, dryRun: boolean = true, shadowOnly: boolean = false) => request<any>(`${BASE_URL}/organize/rename?path=${encodeURIComponent(path)}&dry_run=${dryRun}&shadow_only=${shadowOnly}`, { method: "POST" }),
  scrapeSupplement: (path: string) => request<any>(`${BASE_URL}/organize/supplement?path=${encodeURIComponent(path)}`, { method: "POST" }),
  reorganizeSeasons: (path: string, dryRun: boolean = true) => request<any>(`${BASE_URL}/organize/seasons?path=${encodeURIComponent(path)}&dry_run=${dryRun}`, { method: "POST" }),
  organizeFolder: (path: string, dryRun: boolean = true) => request<any>(`${BASE_URL}/organize/folder?path=${encodeURIComponent(path)}&dry_run=${dryRun}`, { method: "POST" }),
  oneClickOrganize: (path: string, dryRun: boolean = true) => request<any>(`${BASE_URL}/organize/one-click?path=${encodeURIComponent(path)}&dry_run=${dryRun}`, { method: "POST" }),
  // V3 整理 API
  structureOrganize: (path: string, dryRun: boolean = true) => request<any>(`${BASE_URL}/organize/structure?path=${encodeURIComponent(path)}&dry_run=${dryRun}`, { method: "POST" }),
  fullOrganize: (path: string, dryRun: boolean = true, useAi: boolean = false, signal?: AbortSignal) => request<any>(`${BASE_URL}/organize/full?path=${encodeURIComponent(path)}&dry_run=${dryRun}&use_ai=${useAi}`, { method: "POST", signal }),
  fullOrganizeExecute: (path: string, actionPlan: any, useAi: boolean = false) => request<any>(`${BASE_URL}/organize/full?path=${encodeURIComponent(path)}&dry_run=false&use_ai=${useAi}`, { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({action_plan: actionPlan}) }),
  rename: (oldPath: string, newName: string) => request<any>(`${BASE_URL}/rename?old_path=${encodeURIComponent(oldPath)}&new_name=${encodeURIComponent(newName)}`, { method: "POST" }),
  // quickSync 返回 fetch Response，不走 request。
  // signal 用于页面离开 / 切后台时断流（移动端路由页没有"关闭弹窗"这个时机）
  quickSync: (signal?: AbortSignal) => fetch(`${BASE_URL}/sync`, { signal }),

  // 散落季合并
  mergeScatteredSeasons: (path: string, dryRun: boolean = true) =>
    request<any>(`${BASE_URL}/organize/merge-scattered?path=${encodeURIComponent(path)}&dry_run=${dryRun}`, { method: "POST" }),

  // 一键整理 SSE 流式（返回 fetch Response，不走 request）
  organizeFullStream: (path: string, dryRun: boolean = true, useAi: boolean = false) =>
    fetch(`${BASE_URL}/organize/full-stream?path=${encodeURIComponent(path)}&dry_run=${dryRun}&use_ai=${useAi}`, { method: "POST" }),

  // 整理历史
  getOrganizeHistory: (limit: number = 50) =>
    request<any>(`${BASE_URL}/organize/history?limit=${limit}`),
  getOrganizeHistoryDetail: (snapshotId: number) =>
    request<any>(`${BASE_URL}/organize/history/${snapshotId}`),

  rollbackRename: (snapshotId: number) => request<any>(`${BASE_URL}/organize/rollback?snapshot_id=${snapshotId}`, {
    method: "POST",
  }),
};
