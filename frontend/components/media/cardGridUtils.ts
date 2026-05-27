// CardGrid 工具函数和类型定义（从 CardGrid.tsx 拆分）
import type { VideoInfo, FolderNode } from "@/types";

export function getSeasonLabel(name: string): string {
  const m = name.match(/(?:S(\d+)|第(\d+)季|Season\s*(\d+))/i);
  if (m) return `第${parseInt(m[1] || m[2] || m[3])}季`;
  return name;
}

export function getSeasonNum(name: string): number {
  // 阿拉伯数字格式：S01、第3季、Season 2
  const m = name.match(/(?:S(\d+)|第(\d+)季|Season\s*(\d+))/i);
  if (m) return parseInt(m[1] || m[2] || m[3]);
  // 中文数字格式：第一季、第二季...
  const cnMap: Record<string, number> = { "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15, "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20 };
  const cnMatch = name.match(/第([一二三四五六七八九十]+)季/);
  if (cnMatch) return cnMap[cnMatch[1]] || 0;
  return 0;
}

export function compareSeasons(a: FolderNode, b: FolderNode): number {
  const numA = getSeasonNum(a.name);
  const numB = getSeasonNum(b.name);
  if (numA !== numB) return numA - numB;
  return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });
}

export function getSeriesPrefix(name: string): string | null {
  const m = name.match(/^(.+?)[\s._-]*(?:S\d+|第\d+季|Season\s*\d+)$/i);
  return m ? m[1].trim() : null;
}

export type CardItem =
  | { type: "folder"; data: FolderNode; id: string }
  | { type: "video"; data: VideoInfo; id: string }
  | { type: "tv"; seriesName: string; seasons: FolderNode[]; id: string; parentNode?: FolderNode }
  | { type: "series"; data: FolderNode; id: string }
  | { type: "collection"; data: FolderNode; id: string };
