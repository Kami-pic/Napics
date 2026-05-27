// 详情面板模块级缓存：操作状态不随组件卸载丢失

// key = 路径，value = 各种操作的状态
export interface DetailCacheEntry {
  // 一键整理 / 标准结构 / 自动命名等 action 状态
  actionLoading: boolean;
  actionResult: string;
  actionPlan: any;
  abortController: AbortController | null;
  // 刮削状态
  scrapeLoading: boolean;
  scrapeStatus: string;  // "idle" | "loading" | "success" | "failed" | "not_found"
  scrapeData: any;
  // VideoDetail 专用
  renameResult: string;
  structureResult: string;
  // 时间戳
  timestamp: number;
}
const detailCache = new Map<string, Partial<DetailCacheEntry>>();

export function getCached(path: string): Partial<DetailCacheEntry> {
  return detailCache.get(path) || {};
}
export function setCached(path: string, updates: Partial<DetailCacheEntry>) {
  const prev = detailCache.get(path) || {};
  detailCache.set(path, { ...prev, ...updates, timestamp: Date.now() });
}
