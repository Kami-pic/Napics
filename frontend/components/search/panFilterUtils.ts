// 网盘搜索的筛选数据与纯函数 — 与渲染无关，供桌面筛选栏和移动端共用
import type { PanResult } from "@/types";

export interface PanFilterState {
  panType: string[];    // 多选：["quark", "aliyun", ...]
  resolution: string[]; // 多选：["2160p", "1080p", "720p"]
  chineseSubOnly: boolean;
  completeOnly: boolean;
}

export const DEFAULT_PAN_FILTERS: PanFilterState = {
  panType: [], resolution: [], chineseSubOnly: false, completeOnly: false,
};

export function applyPanFilters(results: PanResult[], filters: PanFilterState, disabledSources?: Set<string>): PanResult[] {
  let list = results;
  if (disabledSources && disabledSources.size > 0) {
    list = list.filter(r => !disabledSources.has(r.source));
  }
  const isDefault = filters.panType.length === 0 && filters.resolution.length === 0 && !filters.chineseSubOnly && !filters.completeOnly;
  if (isDefault) return list;
  return list.filter((r) => {
    if (filters.panType.length > 0 && !filters.panType.includes(r.pan_type)) return false;
    if (filters.resolution.length > 0 && !filters.resolution.includes(r.resolution || "")) return false;
    if (filters.completeOnly && !r.is_complete) return false;
    return true;
  });
}

export const PAN_TYPE_COLORS: Record<string, string> = {
  quark: "text-blue-400 bg-blue-400/10", aliyun: "text-orange-400 bg-orange-400/10",
  baidu: "text-green-400 bg-green-400/10", pan115: "text-purple-400 bg-purple-400/10",
  pikpak: "text-red-400 bg-red-400/10", unknown: "text-slate-400 bg-slate-400/10",
};
export const PAN_TYPE_LABELS: Record<string, string> = {
  quark: "夸克", aliyun: "阿里", baidu: "百度", pan115: "115", pikpak: "PikPak", unknown: "未知",
};
export const SOURCE_LABELS: Record<string, string> = {
  pansearch: "PanSearch", pansou: "PanSou", gogopanso: "狗狗盘搜",
  github: "GitHub仓库", rrdynb: "人人电影", ddys: "低端影视",
};
