// 前端 API 统一封装
import type { VideoInfo, AppConfig, FolderNode, AISuggestion, OrganizeSnapshot, AddMediaInfo, IndexerPriority, SortWeightsConfig, AnalysisReport } from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

export const api = {
  getConfig: () => request<AppConfig>(`${BASE_URL}/config`),

  saveConfig: (config: AppConfig) => request<any>(`${BASE_URL}/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  }),

  getLibrary: () => request<VideoInfo[]>(`${BASE_URL}/library`),

  getLibraryTree: () => request<FolderNode>(`${BASE_URL}/library/tree`),

  scan: (path: string, signal?: AbortSignal) =>
    fetch(`${BASE_URL}/scan?path=${encodeURIComponent(path)}`, { signal }),

  search: (query: string) => request<any>(`${BASE_URL}/search?query=${encodeURIComponent(query)}`),

  // 增强搜索（含回退链+二次匹配+全局过滤）
  searchEnhanced: (query: string, options?: {
    media_type?: string; year?: string; shadow_name?: string; clean_name?: string;
    season?: number; total_episodes?: number;
  }) => {
    const p = new URLSearchParams({ query });
    if (options?.media_type) p.set("media_type", options.media_type);
    if (options?.year) p.set("year", options.year);
    if (options?.shadow_name) p.set("shadow_name", options.shadow_name);
    if (options?.clean_name) p.set("clean_name", options.clean_name);
    if (options?.season) p.set("season", String(options.season));
    if (options?.total_episodes) p.set("total_episodes", String(options.total_episodes));
    return request<any>(`${BASE_URL}/search?${p.toString()}`);
  },

  // 单关键词搜索（不回退，供前端逐轮调用）
  // 如果 /search/single 不存在（后端未重启），自动 fallback 到 /search
  searchSingle: async (keyword: string, options?: { media_type?: string; skip_filter?: boolean }) => {
    const p = new URLSearchParams({ keyword });
    if (options?.media_type) p.set("media_type", options.media_type);
    if (options?.skip_filter) p.set("skip_filter", "true");
    try {
      return await request<any>(`${BASE_URL}/search/single?${p.toString()}`);
    } catch {
      // fallback: 用旧的 /search 接口
      const fp = new URLSearchParams({ query: keyword });
      if (options?.media_type) fp.set("media_type", options.media_type);
      const d = await request<any>(`${BASE_URL}/search?${fp.toString()}`);
      return { ...d, keyword };
    }
  },

  download: (url: string, savePath: string, downloadType: "qb" | "alist" = "qb") => request<any>(`${BASE_URL}/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, save_path: savePath, download_type: downloadType }),
  }),

  play: (path: string) => request<any>(`${BASE_URL}/play?path=${encodeURIComponent(path)}`),

  batchManage: (action: "delete" | "move" | "copy" | "remove", paths: string[], targetDir?: string) =>
    request<any>(`${BASE_URL}/batch_manage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, paths, target_dir: targetDir }),
    }),

  getPosterUrl: (name: string) =>
    `${BASE_URL}/movie/poster?name=${encodeURIComponent(name)}`,

  getAISuggestions: () => request<AISuggestion[]>(`${BASE_URL}/ai/suggest`),

  executeAISuggestions: (suggestions: AISuggestion[]) => request<any>(`${BASE_URL}/ai/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(suggestions),
  }),

  getAIHistory: () => request<OrganizeSnapshot[]>(`${BASE_URL}/ai/history`),

  rollbackAI: (snapshotId: number) => request<any>(`${BASE_URL}/ai/rollback?snapshot_id=${snapshotId}`, {
    method: "POST",
  }),

  rollbackRename: (snapshotId: number) => request<any>(`${BASE_URL}/organize/rollback?snapshot_id=${snapshotId}`, {
    method: "POST",
  }),

  // 刮削
  scrape: (name: string, path?: string) => request<any>(`${BASE_URL}/scrape?name=${encodeURIComponent(name)}${path ? `&path=${encodeURIComponent(path)}` : ""}`),
  scrapeCandidates: (name: string) => request<any>(`${BASE_URL}/scrape/candidates?name=${encodeURIComponent(name)}`),
  scrapeSelect: (path: string, tmdbId: number, mediaType: string) => request<any>(`${BASE_URL}/scrape/select?path=${encodeURIComponent(path)}&tmdb_id=${tmdbId}&media_type=${mediaType}`, { method: "POST" }),
  scrapeDoubanCandidates: (name: string) => request<any>(`${BASE_URL}/scrape/douban?name=${encodeURIComponent(name)}`),
  scrapeDoubanSelect: (path: string, doubanId: string, title?: string, year?: string, posterUrl?: string, subtitle?: string) => request<any>(`${BASE_URL}/scrape/douban-select?path=${encodeURIComponent(path)}&douban_id=${doubanId}&title=${encodeURIComponent(title||'')}&year=${encodeURIComponent(year||'')}&poster_url=${encodeURIComponent(posterUrl||'')}&subtitle=${encodeURIComponent(subtitle||'')}`, { method: "POST" }),
  scrapeBangumiCandidates: (name: string) => request<any>(`${BASE_URL}/scrape/bangumi?name=${encodeURIComponent(name)}`),
  scrapeBangumiSelect: (path: string, bgmId: number) => request<any>(`${BASE_URL}/scrape/bangumi-select?path=${encodeURIComponent(path)}&bgm_id=${bgmId}`, { method: "POST" }),
  readScrape: (path: string, noFallback: boolean = false) => request<any>(`${BASE_URL}/scrape/read?path=${encodeURIComponent(path)}${noFallback ? "&no_fallback=true" : ""}`),
  executeScrape: (path: string) => request<any>(`${BASE_URL}/scrape/execute?path=${encodeURIComponent(path)}`, { method: "POST" }),
  batchScrape: (paths: string[]) => request<any>(`${BASE_URL}/scrape/batch`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(paths),
  }),
  uploadPoster: async (path: string, file: File, cover: boolean = false) => {
    const form = new FormData();
    form.append("file", file);
    const coverParam = cover ? "&cover=true" : "";
    const res = await fetch(`${BASE_URL}/scrape/upload-poster?path=${encodeURIComponent(path)}${coverParam}`, { method: "POST", body: form });
    return res.json();
  },
  getLocalPoster: (path: string, cover: boolean = false) => `${BASE_URL}/scrape/poster?path=${encodeURIComponent(path)}${cover ? "&cover=true" : ""}`,

  setPosterFromUrl: (path: string, url: string, cover: boolean = false) => request<any>(`${BASE_URL}/scrape/poster-url?path=${encodeURIComponent(path)}&url=${encodeURIComponent(url)}&cover=${cover}`, { method: "POST" }),

  deletePoster: (path: string) => request<any>(`${BASE_URL}/scrape/delete-poster?path=${encodeURIComponent(path)}`, { method: "POST" }),
  deleteScrape: (path: string) => request<any>(`${BASE_URL}/scrape/delete-scrape?path=${encodeURIComponent(path)}`, { method: "POST" }),

  // 整理
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
  quickSync: () => fetch(`${BASE_URL}/sync`),

  // 备份恢复
  backup: () => fetch(`${BASE_URL}/backup`, { method: "POST" }).then(r => r.blob()),
  restore: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE_URL}/restore`, { method: "POST", body: form });
    return res.json();
  },

  // 禁止刮削
  getNoScrape: () => request<string[]>(`${BASE_URL}/no-scrape`),
  setNoScrape: (path: string, enabled: boolean) => request<any>(`${BASE_URL}/no-scrape?path=${encodeURIComponent(path)}&enabled=${enabled}`, { method: "POST" }),

  // 批量搜索升级（EventSource 流式）
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

  // 豆瓣热榜
  doubanHot: (type: "movie" | "tv", pageStart: number = 0, tag: string = "热门") =>
    request<any>(`${BASE_URL}/douban/hot?type=${encodeURIComponent(type)}&page_start=${pageStart}&tag=${encodeURIComponent(tag)}`),

  // 影片详情（TMDB）
  mediaInfo: (title: string, year: string = "", type: "movie" | "tv" = "movie", subtitle: string = "") =>
    request<any>(`${BASE_URL}/media/info?title=${encodeURIComponent(title)}&year=${encodeURIComponent(year)}&type=${type}&subtitle=${encodeURIComponent(subtitle)}`),

  // 豆瓣搜索
  doubanSearch: (query: string) =>
    request<any>(`${BASE_URL}/douban/search?query=${encodeURIComponent(query)}`),

  // 新增影片（预刮削入库）
  addMedia: (info: AddMediaInfo & { save_path: string }) =>
    request<any>(`${BASE_URL}/add-media`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(info),
    }),

  // 影子名管理
  setShadowName: (path: string, shadowName: string, source: string = "manual") =>
    request<any>(`${BASE_URL}/media/shadow-name`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, shadow_name: shadowName, source }),
    }),

  clearShadowName: (path: string) =>
    request<any>(`${BASE_URL}/media/shadow-name`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    }),

  batchGenerateShadowNames: () =>
    request<any>(`${BASE_URL}/media/shadow-name/batch`, { method: "POST" }),

  // 散落季合并
  mergeScatteredSeasons: (path: string, dryRun: boolean = true) =>
    request<any>(`${BASE_URL}/organize/merge-scattered?path=${encodeURIComponent(path)}&dry_run=${dryRun}`, { method: "POST" }),

  // 索引器优先级管理
  getIndexerPriorities: () =>
    request<IndexerPriority[]>(`${BASE_URL}/config/indexers`),

  saveIndexerPriorities: (indexers: IndexerPriority[]) =>
    request<any>(`${BASE_URL}/config/indexers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ indexers }),
    }),

  // ── 搜索过滤规则配置 ──
  getSearchFilter: () => request<any>(`${BASE_URL}/config/search-filter`),
  saveSearchFilter: (config: Record<string, any>) =>
    request<any>(`${BASE_URL}/config/search-filter`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    }),

  // ── 下载管理 ──
  submitDownload: (task: {
    media_name: string; download_url: string; save_path: string;
    channel?: string; category_hint?: string; is_season_pack?: boolean; season_number?: number;
  }) => request<any>(`${BASE_URL}/download-manager/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(task),
  }),

  getDownloadTasks: (status?: string) =>
    request<any>(`${BASE_URL}/download-manager/tasks${status ? `?status=${status}` : ""}`),

  getDownloadProgress: () => request<any>(`${BASE_URL}/download-manager/progress`),

  syncDownloadProgress: () =>
    request<any>(`${BASE_URL}/download-manager/sync`, { method: "POST" }),

  deleteDownloadTask: (taskId: string) =>
    request<any>(`${BASE_URL}/download-manager/task?task_id=${encodeURIComponent(taskId)}`, { method: "DELETE" }),

  deleteDownloadTasks: (taskIds: string[]) =>
    request<any>(`${BASE_URL}/download-manager/delete-tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(taskIds),
    }),

  recommendChannel: (seeders: number, sizeGb: number) =>
    request<any>(`${BASE_URL}/download-manager/recommend-channel?seeders=${seeders}&size_gb=${sizeGb}`),

  // ── 归位与洗版替换 ──
  organizeDryRun: (taskId: string, autoReplace: boolean = false) => request<any>(`${BASE_URL}/organize/dry-run`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task_id: taskId, auto_replace: autoReplace })
  }),
  organizeExecute: (taskId: string, plan: any) => request<any>(`${BASE_URL}/organize/execute`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task_id: taskId, plan })
  }),

  archiveBoth: (taskId: string, plan: any) => request<any>(`${BASE_URL}/organize/archive-both`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task_id: taskId, plan })
  }),

  purgeOldData: (taskId: string) =>
    request<any>(`${BASE_URL}/organize/purge-old?task_id=${encodeURIComponent(taskId)}`, { method: "POST" }),
  
  cancelReplace: (taskId: string) =>
    request<any>(`${BASE_URL}/download-manager/cancel-replace?task_id=${encodeURIComponent(taskId)}`, { method: "POST" }),

  // ── 回收站 ──
  getRecycleBin: () => request<any>(`${BASE_URL}/recycle-bin`),

  restoreFromBin: (entryId: string) =>
    request<any>(`${BASE_URL}/recycle-bin/restore?entry_id=${encodeURIComponent(entryId)}`, { method: "POST" }),

  cleanupRecycleBin: () =>
    request<any>(`${BASE_URL}/recycle-bin/cleanup`, { method: "POST" }),

  // ══ 二期功能 API ══

  // ── 种子排序权重 ──
  getSortWeights: () => request<SortWeightsConfig>(`${BASE_URL}/config/sort-weights`),
  saveSortWeights: (weights: SortWeightsConfig) =>
    request<any>(`${BASE_URL}/config/sort-weights`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(weights),
    }),

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

  // ── 一键整理 SSE 流式 ──
  organizeFullStream: (path: string, dryRun: boolean = true, useAi: boolean = false) =>
    fetch(`${BASE_URL}/organize/full-stream?path=${encodeURIComponent(path)}&dry_run=${dryRun}&use_ai=${useAi}`, { method: "POST" }),

  // ── 整理历史 ──
  getOrganizeHistory: (limit: number = 50) =>
    request<any>(`${BASE_URL}/organize/history?limit=${limit}`),
  getOrganizeHistoryDetail: (snapshotId: number) =>
    request<any>(`${BASE_URL}/organize/history/${snapshotId}`),

  // ── 网盘搜索 API ──
  searchPan: (keyword: string, mediaType?: string) => {
    const p = new URLSearchParams({ keyword });
    if (mediaType) p.set("media_type", mediaType);
    return request<any>(`${BASE_URL}/search/pan?${p.toString()}`);
  },

  // ── Alist 转存 ──
  alistTransfer: (shareUrl: string, panType: string, savePath: string = "") =>
    request<any>(`${BASE_URL}/alist/transfer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ share_url: shareUrl, pan_type: panType, save_path: savePath }),
    }),

  alistMounts: () => request<any>(`${BASE_URL}/alist/mounts`),
};
