// 字幕搜索状态管理 Hook
"use client";
import { useState, useCallback } from "react";
import {
  subtitleApi,
  type SubtitleDetail,
  type SubtitleSearchItem,
  type SubtitleSearchOptions,
  type SubtitleSource,
  type SubtitleSourceStat,
} from "@/lib/api/subtitle";

// 字幕格式筛选项
export const FORMAT_OPTIONS = ["全部", "SRT", "ASS", "SSA", "SUP", "SUB", "其他"] as const;
export type FormatFilter = (typeof FORMAT_OPTIONS)[number];

// 语言筛选项（含小语种）
export const LANG_OPTIONS = ["全部", "简中", "繁中", "双语", "英文", "日语", "粤语", "韩语", "其他"] as const;
export type LangFilter = (typeof LANG_OPTIONS)[number];

// 来源筛选项
export const SOURCE_OPTIONS = [
  { key: "all", label: "全部来源" },
  { key: "assrt", label: "射手网" },
  { key: "subhd", label: "SubHD" },
  { key: "subdl", label: "SubDL" },
] as const;
export type SourceFilter = (typeof SOURCE_OPTIONS)[number]["key"];

/** 归一化格式：各源返回值不同（assrt 给 "Subrip(srt)"，SubHD 给 "SUP"） */
export function normalizeFormat(subtype: string): FormatFilter {
  const lower = (subtype || "").toLowerCase();
  if (!lower) return "其他";
  if (lower.includes("srt") || lower.includes("subrip")) return "SRT";
  if (lower.includes("ass")) return "ASS";
  if (lower.includes("ssa")) return "SSA";
  if (lower.includes("sup") || lower.includes("pgs")) return "SUP";
  if (lower.includes("vobsub") || lower.includes("sub") || lower.includes("idx")) return "SUB";
  return "其他";
}

/** 归一化语言：assrt 给 "英 简 繁 双语"，SubHD/SubDL 给 "简中"/"双语" */
export function normalizeLang(desc: string): LangFilter {
  const text = desc || "";
  if (!text) return "其他";
  if (text.includes("双语") || text.includes("中英")) return "双语";
  if (text.includes("简")) return "简中";
  if (text.includes("繁")) return "繁中";
  if (text.includes("粤")) return "粤语";
  if (text.includes("日")) return "日语";
  if (text.includes("韩")) return "韩语";
  if (text.includes("英")) return "英文";
  return "其他";
}

export interface SubtitleSearchState {
  results: SubtitleSearchItem[];
  filteredResults: SubtitleSearchItem[];
  sources: SubtitleSourceStat[];
  searching: boolean;
  error: string;
  keyword: string;
  formatFilter: FormatFilter;
  langFilter: LangFilter;
  sourceFilter: SourceFilter;
  /** 智能过滤（盾牌）：隐藏不相关结果 */
  smartFilter: boolean;
  setSmartFilter: (v: boolean) => void;
  /** 被智能过滤隐藏的条数 */
  junkCount: number;
  selected: SubtitleSearchItem | null;
  selectedDetail: SubtitleDetail | null;
  loadingDetail: boolean;
  downloading: boolean;
  downloadMsg: string;
  downloadOk: boolean;
  doSearch: (query: string, options?: SubtitleSearchOptions) => Promise<void>;
  setFormatFilter: (f: FormatFilter) => void;
  setLangFilter: (l: LangFilter) => void;
  setSourceFilter: (s: SourceFilter) => void;
  selectItem: (item: SubtitleSearchItem) => Promise<void>;
  doDownload: (item: SubtitleSearchItem, videoPath: string, fileUrl?: string, langSuffix?: string) => Promise<void>;
  clearSelection: () => void;
}

export function useSubtitleSearch(): SubtitleSearchState {
  const [results, setResults] = useState<SubtitleSearchItem[]>([]);
  const [sources, setSources] = useState<SubtitleSourceStat[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [keyword, setKeyword] = useState("");
  const [formatFilter, setFormatFilter] = useState<FormatFilter>("全部");
  const [langFilter, setLangFilter] = useState<LangFilter>("全部");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  // 默认开启：字幕站搜索词宽松，不过滤时无关结果占比很高
  const [smartFilter, setSmartFilter] = useState(true);
  const [selected, setSelected] = useState<SubtitleSearchItem | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<SubtitleDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadMsg, setDownloadMsg] = useState("");
  const [downloadOk, setDownloadOk] = useState(false);

  const doSearch = useCallback(async (query: string, options?: SubtitleSearchOptions) => {
    setSearching(true);
    setError("");
    setResults([]);
    setSources([]);
    setSelected(null);
    setSelectedDetail(null);
    setDownloadMsg("");
    try {
      const resp = await subtitleApi.search(query, options);
      setResults(resp.results || []);
      setSources(resp.sources || []);
      setKeyword(resp.keyword || query);
    } catch (e: any) {
      setError(e?.message || "搜索失败");
    } finally {
      setSearching(false);
    }
  }, []);

  /** 选中结果：只有 assrt 有详情接口（压缩包文件列表），其他源直接下载 */
  const selectItem = useCallback(async (item: SubtitleSearchItem) => {
    setSelected(item);
    setSelectedDetail(null);
    setDownloadMsg("");
    if (item.source !== "assrt") return;

    setLoadingDetail(true);
    try {
      const resp = await subtitleApi.detail(item.id);
      setSelectedDetail(resp.detail);
    } catch {
      setSelectedDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const doDownload = useCallback(async (
    item: SubtitleSearchItem,
    videoPath: string,
    fileUrl?: string,
    langSuffix?: string,
  ) => {
    setDownloading(true);
    setDownloadMsg("");
    try {
      const resp = await subtitleApi.download({
        subtitle_id: item.id,
        video_path: videoPath,
        source: item.source,
        slug: item.slug || undefined,
        file_url: fileUrl || item.download_url || undefined,
        language_suffix: langSuffix || "",
      });
      setDownloadOk(Boolean(resp.status));
      setDownloadMsg(resp.message || (resp.status ? "下载成功" : "下载失败"));
    } catch (e: any) {
      setDownloadOk(false);
      setDownloadMsg(e?.message || "下载失败");
    } finally {
      setDownloading(false);
    }
  }, []);

  const clearSelection = useCallback(() => {
    setSelected(null);
    setSelectedDetail(null);
    setDownloadMsg("");
  }, []);

  const filteredResults = results.filter((item) => {
    if (smartFilter && item.is_junk) return false;
    if (sourceFilter !== "all" && item.source !== sourceFilter) return false;
    if (formatFilter !== "全部" && normalizeFormat(item.subtype) !== formatFilter) return false;
    if (langFilter !== "全部" && normalizeLang(item.lang?.desc || "") !== langFilter) return false;
    return true;
  });

  const junkCount = results.filter(item => item.is_junk).length;

  return {
    results,
    filteredResults,
    sources,
    searching,
    error,
    keyword,
    formatFilter,
    langFilter,
    sourceFilter,
    smartFilter,
    setSmartFilter,
    junkCount,
    selected,
    selectedDetail,
    loadingDetail,
    downloading,
    downloadMsg,
    downloadOk,
    doSearch,
    setFormatFilter,
    setLangFilter,
    setSourceFilter,
    selectItem,
    doDownload,
    clearSelection,
  };
}
