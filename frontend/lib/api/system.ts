// 系统相关 API
import type { VideoInfo, FolderNode, CompletenessResult, AnalysisReport, MediaLibraryConfig } from "@/types";
import { request, BASE_URL } from "./base";

export const systemApi = {
  getLibrary: () => request<VideoInfo[]>(`${BASE_URL}/library`),
  getLibraryTree: () => request<FolderNode>(`${BASE_URL}/library/tree`),

  /** 视频的外挂字幕文件（下载字幕后刷新字幕状态用） */
  getMediaSubtitles: (path: string) =>
    request<{ status: string; files: string[]; count: number }>(
      `${BASE_URL}/media/subtitles?path=${encodeURIComponent(path)}`,
    ),

  /** 按 NFO 重算标准名（影子名）。手填过的条目不动 */
  generateShadowName: (path: string, isFolder = false) =>
    request<{ status: string; message?: string; updated: number; matched?: number; skipped?: number; shadow_name?: string }>(
      `${BASE_URL}/media/shadow-name/generate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, is_folder: isFolder }),
      },
    ),

  /** 按 NFO / 文件夹名 / 文件名重算检索名（中文+英文） */
  generateCleanName: (path: string, isFolder = false) =>
    request<{ status: string; message?: string; updated: number; matched?: number; reason?: string; cn: string; en: string; display: string }>(
      `${BASE_URL}/library/clean-name/generate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: path, is_folder: isFolder }),
      },
    ),

  // failed[].reason: "missing" | "probe_failed" | "not_in_library"
  // probed 是真的探测成功的条数 —— 后端以前不管成功失败都只回 status: "ok"
  refreshQuality: (paths?: string[]) =>
    request<{
      status: string;
      updated: number;
      total: number;
      probed?: number;
      failed?: { path: string; reason: string }[];
    }>(`${BASE_URL}/library/refresh-quality`, {
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
  scan: (path: string, libraryName?: string, signal?: AbortSignal) => {
    let url = `${BASE_URL}/scan?path=${encodeURIComponent(path)}`;
    if (libraryName) url += `&library_name=${encodeURIComponent(libraryName)}`;
    return fetch(url, { signal });
  },

  // ── 媒体库管理 ──
  listLibraries: () => request<{ libraries: Array<{ name: string; type: string; category_tag: string; paths: string[]; exclude_dirs: string[] }> }>(`${BASE_URL}/library/list`),
  addLibrary: (data: { name: string; category_tag: string; paths: string[]; exclude_dirs: string[] }) =>
    request<{ status: string; name: string }>(`${BASE_URL}/library/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  updateLibrary: (name: string, data: Partial<MediaLibraryConfig>) =>
    request<{ status: string }>(`${BASE_URL}/library/${encodeURIComponent(name)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deleteLibrary: (name: string) =>
    request<{ status: string }>(`${BASE_URL}/library/${encodeURIComponent(name)}`, { method: "DELETE" }),

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

  // ── OpenList ──
  alistTransfer: (shareUrl: string, panType: string, savePath: string = "") =>
    request<any>(`${BASE_URL}/alist/transfer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ share_url: shareUrl, pan_type: panType, save_path: savePath }),
    }),
  alistMounts: () => request<any>(`${BASE_URL}/alist/mounts`),
};
