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

/**
 * 把目录节点聚合成卡片列表（纯函数，无 DOM / state 依赖）。
 * 五种卡片类型的判定规则：虚拟媒体库自身当内容项、folder_type 优先、
 * 无 folder_type 时回退到文件名前缀分组。
 */
export function buildCardItems(
  currentFolder: FolderNode | null,
  groupedVideos: Record<string, VideoInfo[]>,
): CardItem[] {
  if (!currentFolder) return [];
  const results: CardItem[] = [];
  const children = currentFolder.children || [];

  // 虚拟媒体库文件夹内部：把自身当作一个内容项渲染
  // 进入紫色文件夹后，看到的是一个完整的内容卡片（tv/movie/collection），而不是散落的子目录或视频
  if (currentFolder.is_virtual_library) {
    const ft = currentFolder.folder_type || "";
    if (ft === "tv" && children.length > 0) {
      // tv 类型：显示为 tv 卡片，children 作为季目录
      const seasons = [...children].sort(compareSeasons);
      results.push({ type: "tv", seriesName: currentFolder.name, seasons, id: `ms-${currentFolder.path}`, parentNode: currentFolder });
    } else if (ft === "tv" && children.length === 0 && currentFolder.videos?.length > 0) {
      // 扁平 tv（无季目录，直接有视频）
      results.push({ type: "tv", seriesName: currentFolder.name, seasons: [currentFolder], id: `ms-${currentFolder.path}`, parentNode: currentFolder });
    } else if (ft === "movie" && currentFolder.videos?.length === 1) {
      // 单个电影
      const v = currentFolder.videos[0];
      results.push({ type: "video", data: v, id: `v-${v.file_path}-0` });
    } else if ((ft === "collection" || ft === "series") && children.length > 0) {
      // collection/series
      results.push({ type: ft === "series" ? "series" : "collection", data: currentFolder, id: `${ft}-${currentFolder.path}` });
    } else {
      // 其他情况：正常渲染 children 和 videos
      children.forEach(node => results.push({ type: "folder", data: node, id: `f-${node.path}` }));
      Object.entries(groupedVideos).forEach(([, vids]) => {
        vids.forEach((v, vi) => results.push({ type: "video", data: v, id: `v-${v.file_path}-${vi}` }));
      });
    }
    return results;
  }

  const seriesGroups: Record<string, FolderNode[]> = {};
  const standalone: FolderNode[] = [];
  children.forEach(node => {
    const ft = node.folder_type || "";
    // 虚拟媒体库文件夹始终作为独立文件夹卡片显示，不按 folder_type 展开
    if (node.is_virtual_library) {
      standalone.push(node);
      return;
    }
    // 用 folder_type 优先判断
    if (ft === "series") {
      results.push({ type: "series", data: node, id: `sc-${node.path}` });
      return;
    }
    if (ft === "collection") {
      results.push({ type: "collection", data: node, id: `mc-${node.path}` });
      return;
    }
    // tv 类型 → 展开（有子目录显示季卡片，无子目录直接显示集列表）
    if (ft === "tv") {
      if (node.children.length > 0) {
        const seasons = [...node.children].sort(compareSeasons);
        results.push({ type: "tv", seriesName: node.name, seasons, id: `ms-${node.path}`, parentNode: node });
      } else {
        // 扁平 tv（无季目录，直接有视频）→ 当作只有一个虚拟季的 tv
        results.push({ type: "tv", seriesName: node.name, seasons: [node], id: `ms-${node.path}`, parentNode: node });
      }
      return;
    }
    // 兼容旧逻辑：没有 folder_type 时用文件名前缀匹配
    const prefix = getSeriesPrefix(node.name);
    if (prefix) {
      if (!seriesGroups[prefix]) seriesGroups[prefix] = [];
      seriesGroups[prefix].push(node);
    } else { standalone.push(node); }
  });
  Object.entries(seriesGroups).forEach(([name, nodes]) => {
    if (nodes.length > 1) {
      nodes.sort(compareSeasons);
      results.push({ type: "tv", seriesName: name, seasons: nodes, id: `ms-${name}` });
    } else { standalone.push(nodes[0]); }
  });
  // 媒体文件夹置顶，插入到 results 最前面
  const pinned = standalone.filter(n => n.is_virtual_library);
  const normal = standalone.filter(n => !n.is_virtual_library);
  const pinnedItems: CardItem[] = pinned.map(node => ({ type: "folder", data: node, id: `f-${node.path}` }));
  normal.forEach(node => results.push({ type: "folder", data: node, id: `f-${node.path}` }));
  // 将 pinned 插入到 results 最前面
  results.unshift(...pinnedItems);
  Object.entries(groupedVideos).forEach(([, vids]) => {
    vids.forEach((v, vi) => results.push({ type: "video", data: v, id: `v-${v.file_path}-${vi}` }));
  });
  return results;
}
