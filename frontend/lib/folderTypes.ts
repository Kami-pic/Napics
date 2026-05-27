// 文件夹类型 & 标签中文映射

/** 文件夹类型中文名 */
export const FOLDER_TYPE_LABELS: Record<string, string> = {
  movie: "电影",
  collection: "合集",
  series: "系列",
  tv: "剧集",
  season: "季",
  mixed: "混合",
};

/** 一级分类标签中文名 */
export const CATEGORY_TAG_LABELS: Record<string, string> = {
  movie: "电影",
  tv: "剧集",
  anime_tv: "动画番剧",
  anime_movie: "动画电影",
  variety: "综艺",
  other: "其他",
};

/** 标签 → 底层文件结构类型映射 */
export function categoryTagToStructureType(tag: string): "movie" | "tv" {
  if (tag === "tv" || tag === "anime_tv" || tag === "variety") return "tv";
  return "movie"; // movie / anime_movie / other 都按 movie 逻辑
}

/** 一级分类标签下允许的文件夹类型 */
export const ALLOWED_FOLDER_TYPES: Record<string, string[]> = {
  movie: ["movie", "collection", "series", "mixed"],
  tv: ["tv", "season", "mixed"],
  anime_tv: ["tv", "season", "mixed"],
  anime_movie: ["movie", "collection", "series", "mixed"],
  variety: ["tv", "season", "mixed"],
  other: ["movie", "tv", "collection", "series", "mixed"],
};

/** 获取文件夹类型中文标签 */
export function getFolderTypeLabel(ft: string): string {
  return FOLDER_TYPE_LABELS[ft] || ft;
}

/** 获取分类标签中文 */
export function getCategoryTagLabel(tag: string): string {
  return CATEGORY_TAG_LABELS[tag] || tag;
}

/** 是否是聚合容器（不显示刮削信息） */
export function isAggregate(ft: string): boolean {
  return ft === "collection" || ft === "series" || ft === "mixed";
}

/** 是否是末端刮削单元（显示刮削信息） */
export function isScrapeUnit(ft: string): boolean {
  return ft === "movie" || ft === "tv" || ft === "season";
}
