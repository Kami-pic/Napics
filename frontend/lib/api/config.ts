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

  // 备份恢复（backup 返回 blob，不走 request）
  backup: async () => {
    const res = await fetch(`${BASE_URL}/backup`, { method: "POST" });
    // 不检查状态码会把错误 JSON 当成备份文件下给用户，得到一个坏的备份包
    if (!res.ok) throw new Error(`备份失败（${res.status}）`);
    return res.blob();
  },
  restore: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE_URL}/restore`, { method: "POST", body: form });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(detail || `恢复失败（${res.status}）`);
    }
    return res.json();
  },

  // 网页版文件夹选择器：列目录（path 为空时返回根/盘符）
  listDirectories: (path: string = "") =>
    request<{
      path: string;
      parent: string;
      separator: string;
      is_root_list: boolean;
      dirs: { name: string; path: string }[];
      error: string;
    }>(`${BASE_URL}/fs/list?path=${encodeURIComponent(path)}`),

  // 校验路径在服务端是否真实可用（Docker 下常见填了宿主机路径的问题）
  checkPath: (path: string) =>
    request<{
      path: string;
      exists: boolean;
      is_dir: boolean;
      readable: boolean;
      hint: string;
    }>(`${BASE_URL}/fs/check?path=${encodeURIComponent(path)}`),
};
