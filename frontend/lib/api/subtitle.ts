// 字幕搜索与下载 API
import { request, BASE_URL } from "./base";

// ── 类型定义 ──

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

export interface SubtitleSearchResponse {
  status: boolean;
  keyword: string;
  total: number;
  results: SubtitleSearchItem[];
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

// ── API 调用 ──

export const subtitleApi = {
  /** 搜索字幕（智能回退：cn_name → en_name → original_name → query） */
  search: (query: string, options?: {
    cn_name?: string;
    en_name?: string;
    original_name?: string;
    season_number?: number;
    episode_number?: number;
    is_file?: boolean;
    no_muxer?: boolean;
    pos?: number;
    cnt?: number;
  }) => {
    const p = new URLSearchParams();
    if (query) p.set("query", query);
    if (options?.cn_name) p.set("cn_name", options.cn_name);
    if (options?.en_name) p.set("en_name", options.en_name);
    if (options?.original_name) p.set("original_name", options.original_name);
    if (options?.season_number) p.set("season_number", String(options.season_number));
    if (options?.episode_number) p.set("episode_number", String(options.episode_number));
    if (options?.is_file) p.set("is_file", "true");
    if (options?.no_muxer !== false) p.set("no_muxer", "true");
    if (options?.pos !== undefined) p.set("pos", String(options.pos));
    if (options?.cnt !== undefined) p.set("cnt", String(options.cnt));
    return request<SubtitleSearchResponse>(`${BASE_URL}/subtitle/search?${p.toString()}`);
  },

  /** 获取字幕详情（含下载链接和文件列表） */
  detail: (subtitleId: number) =>
    request<SubtitleDetailResponse>(`${BASE_URL}/subtitle/detail?subtitle_id=${subtitleId}`),

  /** 下载字幕到视频同目录 */
  download: (params: {
    subtitle_id: number;
    video_path: string;
    file_url?: string;
    language_suffix?: string;
  }) =>
    request<SubtitleDownloadResponse>(`${BASE_URL}/subtitle/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    }),
};
