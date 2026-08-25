// 刮削相关 API
import { request, BASE_URL } from "./base";

export const scrapeApi = {
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
  // uploadPoster 用 FormData + 直接 fetch，不走 request
  uploadPoster: async (path: string, file: File, cover: boolean = false) => {
    const form = new FormData();
    form.append("file", file);
    const coverParam = cover ? "&cover=true" : "";
    const res = await fetch(`${BASE_URL}/scrape/upload-poster?path=${encodeURIComponent(path)}${coverParam}`, { method: "POST", body: form });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(detail || `封面上传失败（${res.status}）`);
    }
    return res.json();
  },
  /** 远程图片经后端代理加载（后端那侧才有 HTTP 代理，浏览器直连 TMDB 图床会超时） */
  getProxiedImage: (url: string) => `${BASE_URL}/proxy/image?url=${encodeURIComponent(url)}`,

  getLocalPoster: (path: string, cover: boolean = false) => `${BASE_URL}/scrape/poster?path=${encodeURIComponent(path)}${cover ? "&cover=true" : ""}`,

  setPosterFromUrl: (path: string, url: string, cover: boolean = false) => request<any>(`${BASE_URL}/scrape/poster-url?path=${encodeURIComponent(path)}&url=${encodeURIComponent(url)}&cover=${cover}`, { method: "POST" }),

  deletePoster: (path: string) => request<any>(`${BASE_URL}/scrape/delete-poster?path=${encodeURIComponent(path)}`, { method: "POST" }),
  deleteScrape: (path: string) => request<any>(`${BASE_URL}/scrape/delete-scrape?path=${encodeURIComponent(path)}`, { method: "POST" }),
};
