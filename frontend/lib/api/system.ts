// 系统相关 API
import type { VideoInfo, FolderNode, CompletenessResult, AnalysisReport } from "@/types";
import { request, BASE_URL } from "./base";

export const systemApi = {
  getLibrary: () => request<VideoInfo[]>(`${BASE_URL}/library`),
  getLibraryTree: () => request<FolderNode>(`${BASE_URL}/library/tree`),

  refreshQuality: (paths?: string[]) =>
    request<{ status: string; updated: number; total: number }>(`${BASE_URL}/library/refresh-quality`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(paths || null),
    }),

  getCompleteness: (path: string, tmdbId?: number, refresh?: boolean) => {
    let url = `${BASE_URL}/library/completeness?path=${encodeURIComponent(path)}`;
    if (tmdbId) url += `&tmdb_id=${tmdbId}`;
    if (refresh) url += `&refresh=true`;
    return request<CompletenessResult>(url);
  },

  // scan 返回 fetch Response，不走 request
  scan: (path: string, signal?: AbortSignal) =>
    fetch(`${BASE_URL}/scan?path=${encodeURIComponent(path)}`, { signal }),

  play: (path: string) => request<any>(`${BASE_URL}/play?path=${encodeURIComponent(path)}`),

  batchManage: (action: "delete" | "move" | "copy" | "remove", paths: string[], targetDir?: string) =>
    request<any>(`${BASE_URL}/batch_manage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, paths, target_dir: targetDir }),
    }),

  // ── 回收站 ──
  getRecycleBin: () => request<any>(`${BASE_URL}/recycle-bin`),
  restoreFromBin: (entryId: string) =>
    request<any>(`${BASE_URL}/recycle-bin/restore?entry_id=${encodeURIComponent(entryId)}`, { method: "POST" }),
  cleanupRecycleBin: () =>
    request<any>(`${BASE_URL}/recycle-bin/cleanup`, { method: "POST" }),

  // ── 种子黑名单 ──
  getBlacklist: () => request<any>(`${BASE_URL}/torrent-blacklist`),
  addToBlacklist: (url: string) =>
    request<any>(`${BASE_URL}/torrent-blacklist/add?url=${encodeURIComponent(url)}`, { method: "POST" }),
  removeFromBlacklist: (url: string) =>
    request<any>(`${BASE_URL}/torrent-blacklist/remove?url=${encodeURIComponent(url)}`, { method: "POST" }),
  checkBlacklist: (url: string) =>
    request<{ blocked: boolean }>(`${BASE_URL}/torrent-blacklist/check?url=${encodeURIComponent(url)}`),

  // ── 全库分析报告 ──
  getAnalysisReport: (force: boolean = false) =>
    request<AnalysisReport>(`${BASE_URL}/analysis/report?force=${force}`),
  invalidateAnalysisCache: () =>
    request<any>(`${BASE_URL}/analysis/invalidate`, { method: "POST" }),

  restartSystem: () => request<any>(`${BASE_URL}/api/system/restart`, { method: "POST" }),

  // ── Alist ──
  alistTransfer: (shareUrl: string, panType: string, savePath: string = "") =>
    request<any>(`${BASE_URL}/alist/transfer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ share_url: shareUrl, pan_type: panType, save_path: savePath }),
    }),
  alistMounts: () => request<any>(`${BASE_URL}/alist/mounts`),
};
