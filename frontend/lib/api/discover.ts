// 发现推荐相关 API
import type { AddMediaInfo } from "@/types";
import { request, BASE_URL } from "./base";

export const discoverApi = {
  // 豆瓣热榜
  doubanHot: (type: "movie" | "tv", pageStart: number = 0, tag: string = "热门") =>
    request<any>(`${BASE_URL}/douban/hot?type=${encodeURIComponent(type)}&page_start=${pageStart}&tag=${encodeURIComponent(tag)}`),

  // 影片详情（TMDB）
  mediaInfo: (title: string, year: string = "", type: "movie" | "tv" = "movie", subtitle: string = "", source: string = "tmdb", id: string = "") =>
    request<any>(`${BASE_URL}/media/info?title=${encodeURIComponent(title)}&year=${encodeURIComponent(year)}&type=${type}&subtitle=${encodeURIComponent(subtitle)}&source=${source}&id=${encodeURIComponent(id)}`),

  // 豆瓣搜索
  doubanSearch: (query: string) =>
    request<any>(`${BASE_URL}/douban/search?query=${encodeURIComponent(query)}`),

  // ── 发现推荐 API ──
  discoverRecommend: (source: string, start: number = 0, count: number = 20) =>
    request<any>(`${BASE_URL}/discover/recommend/${source}?start=${start}&count=${count}`),

  discoverExplore: (provider: string = "douban", type: string = "movie", sort: string = "T", tags: string = "", page: number = 0, count: number = 20, language: string = "", year: string = "", voteAverage: number = 0, area: string = "", cat: string = "", voteMax: number = 10) => {
    const p = new URLSearchParams({ provider, type, sort, page: String(page), count: String(count) });
    // 豆瓣 tags 拼接：风格+地区+年代（豆瓣 API 用逗号分隔多个标签）
    const tagParts = [tags, area, provider === "douban" ? year : ""].filter(Boolean);
    if (provider === "douban" && tagParts.length > 0) {
      p.set("tags", tagParts.join(","));
    } else if (tags) {
      p.set("tags", tags);
    }
    if (language) p.set("with_original_language", language);
    if (year && provider !== "douban") p.set("year", year);
    if (voteAverage > 0) p.set("vote_average", String(voteAverage));
    if (voteMax < 10) p.set("vote_max", String(voteMax));
    if (cat) p.set("cat", cat);
    return request<any>(`${BASE_URL}/discover/explore?${p.toString()}`);
  },

  discoverSources: () => request<any>(`${BASE_URL}/discover/sources`),

  discoverRefresh: (source: string) =>
    request<any>(`${BASE_URL}/discover/refresh/${source}`, { method: "POST" }),

  // 新增影片（预刮削入库）
  addMedia: (info: AddMediaInfo & { save_path: string }) =>
    request<any>(`${BASE_URL}/add-media`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(info),
    }),

  getPosterUrl: (name: string) =>
    `${BASE_URL}/movie/poster?name=${encodeURIComponent(name)}`,
};
