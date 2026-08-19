// 字幕搜索状态管理 Hook
"use client";
import { useState, useCallback } from "react";
import { subtitleApi, type SubtitleSearchItem, type SubtitleDetail } from "@/lib/api/subtitle";

// 字幕格式筛选选项
export const FORMAT_OPTIONS = ["全部", "SRT", "ASS", "SSA", "SUP", "SUB", "其他"] as const;
export type FormatFilter = (typeof FORMAT_OPTIONS)[number];

// 语言筛选选项
export const LANG_OPTIONS = ["全部", "简中", "繁中", "英文", "日语", "粤语", "韩语", "双语", "其他"] as const;
export type LangFilter = (typeof LANG_OPTIONS)[number];

/** 解析 assrt subtype 字段为标准格式名 */
function parseSubtype(subtype: string): string {
  const lower = subtype.toLowerCase();
  if (lower.includes("srt") || lower.includes("subrip")) return "SRT";
  if (lower.includes("ass")) return "ASS";
  if (lower.includes("ssa")) return "SSA";
  if (lower.includes("vobsub") || lower.includes("sub")) return "SUB";
  if (lower.includes("sup") || lower.includes("pgs")) return "SUP";
  return "其他";
}

/** 解析语言描述 */
function parseLang(lang: { desc: string; langlist: Record<string, boolean> }): string {
  const desc = lang.desc || "";
  const list = lang.langlist || {};
  // 优先用 langlist 判断
  if (list.langchs || desc.includes("简")) return "简中";
  if (list.langcht || desc.includes("繁")) return "繁中";
  if (list.langdou || desc.includes("双")) return "双语";
  if (list.langeng || desc.includes("英")) return "英文";
  if (list.langjap || desc.includes("日")) return "日语";
  if (list.langkor || desc.includes("韩")) return "韩语";
  if (desc.includes("粤")) return "粤语";
  return "其他";
}

export interface SubtitleSearchState {
  results: SubtitleSearchItem[];
  searching: boolean;
  error: string;
  keyword: string;
  formatFilter: FormatFilter;
  langFilter: LangFilter;
  filteredResults: SubtitleSearchItem[];
  selectedDetail: SubtitleDetail | null;
  loadingDetail: boolean;
  downloading: boolean;
  downloadMsg: string;
  doSearch: (query: string, options?: { cn_name?: string; en_name?: string; original_name?: string; season_number?: number; episode_number?: number; is_file?: boolean }) => Promise<void>;
  setFormatFilter: (f: FormatFilter) => void;
  setLangFilter: (l: LangFilter) => void;
  fetchDetail: (id: number) => Promise<void>;
  doDownload: (subtitleId: number, videoPath: string, fileUrl?: string, langSuffix?: string) => Promise<void>;
  clearDetail: () => void;
}

export function useSubtitleSearch(): SubtitleSearchState {
  const [results, setResults] = useState<SubtitleSearchItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [keyword, setKeyword] = useState("");
  const [formatFilter, setFormatFilter] = useState<FormatFilter>("全部");
  const [langFilter, setLangFilter] = useState<LangFilter>("全部");
  const [selectedDetail, setSelectedDetail] = useState<SubtitleDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadMsg, setDownloadMsg] = useState("");

  const doSearch = useCallback(async (query: string, options?: { cn_name?: string; en_name?: string; original_name?: string; season_number?: number; episode_number?: number; is_file?: boolean }) => {
    setSearching(true);
    setError("");
    setResults([]);
    setSelectedDetail(null);
    try {
      const resp = await subtitleApi.search(query, options);
      setResults(resp.results || []);
      setKeyword(resp.keyword || query);
    } catch (e: any) {
      setError(e.message || "搜索失败");
    } finally {
      setSearching(false);
    }
  }, []);

  const fetchDetail = useCallback(async (id: number) => {
    setLoadingDetail(true);
    try {
      const resp = await subtitleApi.detail(id);
      setSelectedDetail(resp.detail);
    } catch {
      setSelectedDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const doDownload = useCallback(async (subtitleId: number, videoPath: string, fileUrl?: string, langSuffix?: string) => {
    setDownloading(true);
    setDownloadMsg("");
    try {
      const resp = await subtitleApi.download({
        subtitle_id: subtitleId,
        video_path: videoPath,
        file_url: fileUrl,
        language_suffix: langSuffix || "",
      });
      setDownloadMsg(resp.message || (resp.status ? "下载成功" : "下载失败"));
    } catch (e: any) {
      setDownloadMsg(e.message || "下载失败");
    } finally {
      setDownloading(false);
    }
  }, []);

  const clearDetail = useCallback(() => setSelectedDetail(null), []);

  // 筛选逻辑
  const filteredResults = results.filter((item) => {
    // 格式筛选
    if (formatFilter !== "全部") {
      const fmt = parseSubtype(item.subtype);
      if (fmt !== formatFilter) return false;
    }
    // 语言筛选
    if (langFilter !== "全部") {
      const lng = parseLang(item.lang);
      if (lng !== langFilter) return false;
    }
    return true;
  });

  return {
    results,
    searching,
    error,
    keyword,
    formatFilter,
    langFilter,
    filteredResults,
    selectedDetail,
    loadingDetail,
    downloading,
    downloadMsg,
    doSearch,
    setFormatFilter,
    setLangFilter,
    fetchDetail,
    doDownload,
    clearDetail,
  };
}
