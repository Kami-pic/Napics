// 媒体库内检索：在已经拿到的整棵树里按名字找条目。
//
// 纯前端过滤，不打后端：整树已经在内存里（应用级 Provider 缓存），
// 而 2600 个视频的遍历是微秒级的。后端也没有"按名字搜媒体库"的端点。
//
// 匹配的是**原始目录名与文件名**（显示什么就搜什么），外加清洗名作为补充 ——
// 用户可能记得的是「三体」而目录叫 `Three-Body.2023.2160p...`。
import type { FolderNode, VideoInfo } from "@/types";

/** 一条命中。目录和视频的去向不同，所以类型要区分 */
export type MobileLibraryHit =
  | { kind: "folder"; node: FolderNode }
  | { kind: "video"; video: VideoInfo };

/** 结果上限。三列卡片下 90 条已经是 30 行，再多没人翻，还会拖慢渲染 */
export const LIBRARY_SEARCH_LIMIT = 90;

/** 字段可能缺失（旧条目没有 clean_name / shadow_name），一律按空串处理 */
function normalize(text: string | undefined): string {
  return (text || "").toLowerCase();
}

function folderMatches(node: FolderNode, needle: string): boolean {
  return normalize(node.name).includes(needle) || normalize(node.clean_name).includes(needle);
}

function videoMatches(video: VideoInfo, needle: string): boolean {
  return normalize(video.file_name).includes(needle)
    || normalize(video.clean_name).includes(needle)
    || normalize(video.shadow_name).includes(needle);
}

export interface MobileLibrarySearchResult {
  hits: MobileLibraryHit[];
  /** 命中总数（可能超过上限），用来告诉用户"还有更多，把词写细一点" */
  total: number;
  truncated: boolean;
}

/**
 * 全树检索。
 *
 * 命中一个目录之后**不再往它下面找**：搜「三体」时用户要的是那部剧，
 * 不是它下面 30 集各算一条把结果冲掉。
 */
export function searchLibrary(root: FolderNode | null, query: string): MobileLibrarySearchResult {
  const needle = normalize(query).trim();
  if (!root || !needle) return { hits: [], total: 0, truncated: false };

  const hits: MobileLibraryHit[] = [];
  let total = 0;

  const walk = (node: FolderNode) => {
    for (const child of node.children || []) {
      if (folderMatches(child, needle)) {
        total += 1;
        if (hits.length < LIBRARY_SEARCH_LIMIT) hits.push({ kind: "folder", node: child });
        // 命中目录就不再深入，避免它下面的每一集又各占一条
        continue;
      }
      walk(child);
    }
    for (const video of node.videos || []) {
      if (!videoMatches(video, needle)) continue;
      total += 1;
      if (hits.length < LIBRARY_SEARCH_LIMIT) hits.push({ kind: "video", video });
    }
  };

  walk(root);
  return { hits, total, truncated: total > hits.length };
}
