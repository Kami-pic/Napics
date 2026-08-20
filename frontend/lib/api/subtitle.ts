// 字幕搜索与下载 API
import { request, BASE_URL } from "./base";

// ── 类型定义 ──

export type SubtitleSource = "assrt" | "subhd" | "subdl";

export interface SubtitleLang {
  desc: string;
  langlist: Record<string, boolean>;
}

export interface SubtitleSearchItem {
  id: number;
  native_name: string;
  videoname: string;
  subtype: string;
  upload_time: string;
  vote_score: number;
  release_site: string;
  lang: SubtitleLang;
  revision: number;
  source: SubtitleSource;
  download_url: string;
  slug: string;
  hit_keyword: string;
  file_size: string;
}

export interface SubtitleFileItem {
  f: string;
  s: string;
  url: string;
}

export interface SubtitleDetail {
  id: number;
  native_name: string;
  filename: string;
  title: string;
  url: string;
  size: number;
  subtype: string;
  upload_time: string;
  vote_score: number;
  release_site: string;
  lang: SubtitleLang;
  filelist: SubtitleFileItem[];
  down_count: number;
  view_count: number;
}

/** 单个源的搜索情况（搜了哪些词、哪个词命中） */
export interface SubtitleSourceStat {
  source: SubtitleSource;
  searched_keywords: string[];
  hit_keyword: string;
  count: number;
  error: string;
}

export interface SubtitleSearchResponse {
  status: boolean;
  keyword: string;
  total: number;
  results: SubtitleSearchItem[];
  sources: SubtitleSourceStat[];
}

export interface SubtitleDetailResponse {
  status: boolean;
  detail: SubtitleDetail | null;
}

export interface SubtitleDownloadResponse {
  status: boolean;
  saved_files: string[];
  message: string;
}

export interface SubtitleSourceStatus {
  id: SubtitleSource;
  name: string;
  configured: boolean;
  requires_config: string;
}

/** 搜索参数：与「搜索升级」同一套输入，后端据此生成 中文/中文+英文/英文 回退链 */
export interface SubtitleSearchOptions {
  cn_name?: string;
  en_name?: string;
  original_name?: string;
  folder_type?: string;
  season_number?: number;
  episode_number?: number;
  episode_tag?: string;
  is_file?: boolean;
  cnt?: number;
}

// ── API 调用 ──

export const subtitleApi = {
  /** 三源搜索字幕（assrt + SubHD + SubDL 并发，各源走自己的回退链） */
  search: (query: string, options?: SubtitleSearchOptions) => {
    const p = new URLSearchParams();
    if (query) p.set("query", query);
    if (options?.cn_name) p.set("cn_name", options.cn_name);
    if (options?.en_name) p.set("en_name", options.en_name);
    if (options?.original_name) p.set("original_name", options.original_name);
    if (options?.folder_type) p.set("folder_type", options.folder_type);
    if (options?.season_number) p.set("season_number", String(options.season_number));
    if (options?.episode_number) p.set("episode_number", String(options.episode_number));
    if (options?.episode_tag) p.set("episode_tag", options.episode_tag);
    if (options?.is_file) p.set("is_file", "true");
    if (options?.cnt !== undefined) p.set("cnt", String(options.cnt));
    return request<SubtitleSearchResponse>(`${BASE_URL}/subtitle/search?${p.toString()}`);
  },

  /** 各源配置状态 */
  getSources: () => request<SubtitleSourceStatus[]>(`${BASE_URL}/subtitle/sources`),

  /** assrt 字幕详情（含压缩包内文件列表），其他源无此接口 */
  detail: (subtitleId: number) =>
    request<SubtitleDetailResponse>(`${BASE_URL}/subtitle/detail?subtitle_id=${subtitleId}`),

  /** 下载字幕到视频同目录 */
  download: (params: {
    subtitle_id: number;
    video_path: string;
    source: SubtitleSource;
    slug?: string;
    file_url?: string;
    language_suffix?: string;
  }) =>
    request<SubtitleDownloadResponse>(`${BASE_URL}/subtitle/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    }),
};
