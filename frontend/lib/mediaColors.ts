// 媒体类型颜色规范 — 全局统一，所有组件引用此文件
// 类型标签颜色（bg + text）
// 评分品牌色（text only）

/** 媒体类型 → 标签颜色 */
export function getMediaTypeColor(type: string): { bg: string; text: string; label: string } {
  switch (type) {
    case "movie":
    case "电影":
      return { bg: "bg-blue-500/20", text: "text-blue-400", label: "电影" };
    case "tv":
    case "剧集":
    case "电视剧":
      return { bg: "bg-green-500/20", text: "text-green-400", label: "剧集" };
    case "动画":
      return { bg: "bg-purple-500/20", text: "text-purple-400", label: "动画" };
    case "书籍":
      return { bg: "bg-pink-500/20", text: "text-pink-400", label: "书籍" };
    case "游戏":
      return { bg: "bg-orange-500/20", text: "text-orange-400", label: "游戏" };
    case "音乐":
      return { bg: "bg-cyan-500/20", text: "text-cyan-400", label: "音乐" };
    case "三次元":
      return { bg: "bg-amber-500/20", text: "text-amber-400", label: "三次元" };
    default:
      return { bg: "bg-white/[0.08]", text: "text-slate-400", label: type || "未知" };
  }
}

/** 评分来源 → 品牌色 */
export function getRatingColor(source: "douban" | "tmdb" | "bangumi"): string {
  switch (source) {
    case "douban": return "text-green-400";
    case "tmdb": return "text-blue-400";
    case "bangumi": return "text-pink-400";
  }
}

/** 获取评分星星的 CSS 类 */
export function getRatingStarClass(source: "douban" | "tmdb" | "bangumi"): string {
  return getRatingColor(source);
}
