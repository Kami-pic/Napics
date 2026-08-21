// BT 搜索的筛选数据与纯函数 — 与渲染无关，供桌面筛选栏和移动端共用
import type { FilterState, EnhancedSearchResult } from "@/types";

// ── 品牌色 ──
export const INDEXER_DOT_COLOR: Record<string, string> = {
  prowlarr: "bg-slate-400", bitsearch: "bg-blue-500", cilixiong: "bg-orange-500",
  xl720: "bg-orange-500", nyaa: "bg-purple-500", mikan: "bg-pink-500",
  yts: "bg-green-500", limetorrents: "bg-lime-500", acgrip: "bg-cyan-500",
  bangumi_moe: "bg-rose-500", eztv: "bg-sky-500", dmhy: "bg-red-500",
  "1337x": "bg-teal-500",
};
export const INDEXER_TAG_STYLE: Record<string, string> = {
  bitsearch: "bg-blue-500/15 text-blue-400", cilixiong: "bg-orange-500/15 text-orange-400",
  xl720: "bg-orange-500/15 text-orange-400", nyaa: "bg-purple-500/15 text-purple-400",
  mikan: "bg-pink-500/15 text-pink-400", yts: "bg-green-500/15 text-green-400",
  limetorrents: "bg-lime-500/15 text-lime-400", acgrip: "bg-cyan-500/15 text-cyan-400",
  bangumi_moe: "bg-rose-500/15 text-rose-400", eztv: "bg-sky-500/15 text-sky-400",
  dmhy: "bg-red-500/15 text-red-400", "1337x": "bg-teal-500/15 text-teal-400",
};

export interface SourceStatus {
  status: "idle" | "searching" | "done" | "failed";
  count: number;
}

// ── 默认筛选 ──
export const DEFAULT_FILTERS: FilterState = {
  resolution: [], source: [], videoCodec: [], audioCodec: [],
  chineseSubOnly: false, seasonPackOnly: false,
  minSizeGb: null, maxSizeGb: null, minSeeders: 0, indexers: [],
};

// ── 整季包判断 ──
const isSeasonPack = (title: string) => /S\d{2}/i.test(title) && !/E\d{2}/i.test(title);

// ── 筛选逻辑 ──
export function applyFilters(results: EnhancedSearchResult[], filters: FilterState, disabledSources?: Set<string>, noSeederInfoSources?: Set<string>, indexerProviderSources?: Set<string>): EnhancedSearchResult[] {
  let list = results;
  if (disabledSources && disabledSources.size > 0) {
    list = list.filter(r => {
      const source = (r as any)._source || r.indexer;
      return !disabledSources.has(source);
    });
  }
  const isDefault = filters.resolution.length === 0 && filters.source.length === 0 &&
    filters.videoCodec.length === 0 && filters.audioCodec.length === 0 &&
    !filters.chineseSubOnly && !filters.seasonPackOnly &&
    filters.minSizeGb === null && filters.maxSizeGb === null &&
    filters.minSeeders <= 0 && filters.indexers.length === 0;
  if (isDefault) return list;
  return list.filter((r) => {
    if (filters.resolution.length > 0) {
      const res = r.quality?.resolution || "";
      if (!filters.resolution.includes(res)) return false;
    }
    if (filters.source.length > 0 && !filters.source.includes(r.quality?.source || "")) return false;
    if (filters.videoCodec.length > 0 && !filters.videoCodec.includes(r.quality?.video_codec || "")) return false;
    if (filters.audioCodec.length > 0) {
      const ac = r.quality?.audio_codec || "";
      const isSurround = r.quality?.is_surround ?? false;
      const match = filters.audioCodec.includes(ac) || (filters.audioCodec.includes("surround") && isSurround);
      if (!match) return false;
    }
    if (filters.chineseSubOnly && !r.quality?.has_chinese_sub) return false;
    if (filters.seasonPackOnly && !isSeasonPack(r.title)) return false;
    if (filters.minSizeGb !== null && r.size_gb < filters.minSizeGb) return false;
    if (filters.maxSizeGb !== null && r.size_gb > filters.maxSizeGb) return false;
    if (filters.minSeeders > 0 && r.seeders < filters.minSeeders) {
      // 磁力链接源（seeders=0 且 size=0）不受做种数筛选影响
      const isMagnetOnly = r.seeders === 0 && r.size_gb === 0;
      const source = (r as any)._source || "";
      const hasNoSeederInfo = noSeederInfoSources?.has(source) ?? false;
      if (!isMagnetOnly && !hasNoSeederInfo) return false;
    }
    if (filters.indexers.length > 0) {
      // 索引器筛选：只对带 indexers 能力的聚合 provider 生效，直搜源不受影响
      const source = (r as any)._source || r.indexer;
      if ((indexerProviderSources?.has(source) ?? false) && !filters.indexers.includes(r.indexer)) return false;
    }
    return true;
  });
}
