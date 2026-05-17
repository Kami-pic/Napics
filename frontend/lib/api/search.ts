// 搜索相关 API
import { request, BASE_URL } from "./base";

export const searchApi = {
  search: (query: string) => request<any>(`${BASE_URL}/api/search?query=${encodeURIComponent(query)}`),

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

  // SSE 流式搜索（逐源返回进度）
  searchStream: (keyword: string, options?: { media_type?: string; cn_name?: string; en_name?: string; original_name?: string; season_number?: number }) => {
    const p = new URLSearchParams({ query: keyword });
    if (options?.media_type) p.set("media_type", options.media_type);
    if (options?.cn_name) p.set("cn_name", options.cn_name);
    if (options?.en_name) p.set("en_name", options.en_name);
    if (options?.original_name) p.set("original_name", options.original_name);
    if (options?.season_number) p.set("season_number", String(options.season_number));
    return `${BASE_URL}/api/search/stream?${p.toString()}`;
  },

  // 单源搜索（指定源 + 搜索词 + 可选回退词）
  searchSource: (source: string, keyword: string, fallbackKeywords?: string) =>
    request<any>(`${BASE_URL}/api/search/source?source=${encodeURIComponent(source)}&keyword=${encodeURIComponent(keyword)}${fallbackKeywords ? `&fallback_keywords=${encodeURIComponent(fallbackKeywords)}` : ""}`),

  // ── 网盘搜索 API ──
  searchPan: (keyword: string, mediaType?: string) => {
    const p = new URLSearchParams({ keyword });
    if (mediaType) p.set("media_type", mediaType);
    return request<any>(`${BASE_URL}/search/pan?${p.toString()}`);
  },

  // ── 搜索源管理 ──
  getProviders: () => request<any>(`${BASE_URL}/api/providers`),
  getSearchSources: () => request<any>(`${BASE_URL}/search/sources`),
  toggleSearchSource: (name: string, enabled: boolean) =>
    request<any>(`${BASE_URL}/search/sources/${name}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    }),
  toggleSearchSourceProxy: (name: string, proxy: boolean) =>
    request<any>(`${BASE_URL}/search/sources/${name}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ proxy }),
    }),
};
