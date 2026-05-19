// 配置相关 API
import type { AppConfig, IndexerPriority, SortWeightsConfig } from "@/types";
import { request, BASE_URL } from "./base";

export const configApi = {
  getConfig: () => request<AppConfig>(`${BASE_URL}/config`),
  saveConfig: (config: AppConfig) => request<any>(`${BASE_URL}/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  }),

  // ── 搜索过滤规则配置 ──
  getSearchFilter: () => request<any>(`${BASE_URL}/config/search-filter`),
  saveSearchFilter: (config: Record<string, any>) =>
    request<any>(`${BASE_URL}/config/search-filter`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    }),

  // ── 种子排序权重 ──
  getSortWeights: () => request<SortWeightsConfig>(`${BASE_URL}/config/sort-weights`),
  saveSortWeights: (weights: SortWeightsConfig) =>
    request<any>(`${BASE_URL}/config/sort-weights`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(weights),
    }),

  // 索引器优先级管理
  getIndexerPriorities: () =>
    request<IndexerPriority[]>(`${BASE_URL}/config/indexers`),
  saveIndexerPriorities: (indexers: IndexerPriority[]) =>
    request<any>(`${BASE_URL}/config/indexers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ indexers }),
    }),

  // 禁止刮削
  getNoScrape: () => request<string[]>(`${BASE_URL}/no-scrape`),
  setNoScrape: (path: string, enabled: boolean) => request<any>(`${BASE_URL}/no-scrape?path=${encodeURIComponent(path)}&enabled=${enabled}`, { method: "POST" }),

  // 备份恢复（backup 返回 fetch Response，不走 request）
  backup: () => fetch(`${BASE_URL}/backup`, { method: "POST" }).then(r => r.blob()),
  restore: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE_URL}/restore`, { method: "POST", body: form });
    return res.json();
  },

  // 文件夹选择器
  browseFolder: () => request<{ path: string }>(`${BASE_URL}/config/browse-folder`),
};
