// 媒体库树导航域：把 /library/tree 的节点翻译成"这一屏该显示什么、点了去哪"。
//
// 纯函数，不碰 React，不碰路由跳转 —— 行为矩阵（TODO §六 十行）在这里可穷举测试，
// 页面只负责渲染和调 router。
//
// 树结构的关键口径（来自 backend/routes/library_tree.py，不是猜的）：
// - 剧 = folder_type "tv"；季 = 它的 children（post_process 把 tv 的子节点**强行改写**成
//   "season"）；集 = 季节点的 videos。
// - **存在无季目录的扁平剧**：folder_type 为 "tv" 但 children 为空，videos 直接是集。
// - collection / series 可能同时有 children 和自己的 videos，两段都要渲染，
//   否则会出现"卡片点了没反应"。
import type { FolderNode, VideoInfo } from "@/types";
import { naturalCompare } from "@/lib/utils";
import { libraryUrl, libraryDetailUrl } from "./mobileRouteUtils";

/** 这一屏的主呈现形态。folders 与 videos 两段可以同时非空 */
export type MobileLibraryViewKind = "folders" | "seasons" | "episodes";

export interface MobileLibraryView {
  kind: MobileLibraryViewKind;
  /** 子目录卡片（已排序）。kind 为 seasons 时就是季节点 */
  folders: FolderNode[];
  /** 正片：季内集，或本目录的直属视频（已自然排序） */
  videos: VideoInfo[];
  /**
   * 剧目录下的散片（剧场版、SP、没归进季目录的集）。
   *
   * 单独一段而不是接在 `videos` 后面：集列表打的是位置序号，混在一起
   * `SP 特别篇.mkv` 会顶着"03"排在 S01E02 后面，看起来像第 3 集。
   */
  extraVideos: VideoInfo[];
  /** 页头主标题 */
  title: string;
  /** 页头副标题：单季剧显示季名，其他情况为空 */
  subtitle: string;
  /** folders 与 videos 都空 —— 页面显示空态而不是白屏 */
  isEmpty: boolean;
}

/** 点击一个节点该去哪 */
export type MobileNavTarget =
  | { type: "library"; url: string }
  | { type: "detail"; url: string };

/** 节点显示名：优先清洗名。清洗名可能为空串，不能用 ?? */
export function nodeDisplayName(node: FolderNode): string {
  return node.clean_name || node.name || "";
}

/** 视频显示名：优先清洗名，回退文件名 */
export function videoDisplayName(video: VideoInfo): string {
  return video.clean_name || video.file_name || "";
}

/** 按 path 在树里找节点。根节点 path 是空串，所以空 path 直接返回根 */
export function findNode(root: FolderNode | null, targetPath: string): FolderNode | null {
  if (!root) return null;
  if (!targetPath) return root;
  const stack: FolderNode[] = [root];
  while (stack.length) {
    const current = stack.pop()!;
    if (current.path === targetPath) return current;
    for (const child of current.children || []) stack.push(child);
  }
  return null;
}

/** 按 file_path 找视频条目。详情页与播放页只拿到路径，元信息要从树里取 */
export function findVideoByPath(root: FolderNode | null, filePath: string): VideoInfo | null {
  if (!root || !filePath) return null;
  const stack: FolderNode[] = [root];
  while (stack.length) {
    const current = stack.pop()!;
    for (const video of current.videos || []) {
      if (video.file_path === filePath) return video;
    }
    for (const child of current.children || []) stack.push(child);
  }
  return null;
}

/**
 * 找父节点的 path，给页头返回键当 fallback 目标。
 *
 * 不能只 `router.back()`：从别处直达（分享链接、通知）时历史栈里没有上一级，
 * back 会退出应用。返回根（path 为空串）时返回空串，页面据此仍指向 /m/library。
 * 找不到节点或节点就是根时返回 null，页头不渲染返回键。
 */
export function findParentPath(root: FolderNode | null, targetPath: string): string | null {
  if (!root || !targetPath) return null;
  const stack: FolderNode[] = [root];
  while (stack.length) {
    const current = stack.pop()!;
    for (const child of current.children || []) {
      if (child.path === targetPath) return current.path;
      stack.push(child);
    }
  }
  return null;
}

/**
 * 是不是"单电影"节点。
 *
 * 矩阵要求单电影点击进详情而不是再下钻一层空目录。判定要同时看结构而不是只看
 * folder_type：手动覆盖过 folder_type 的目录里可能塞了好几个文件。
 */
export function isSingleMovieNode(node: FolderNode): boolean {
  const videos = node.videos || [];
  const children = node.children || [];
  return node.folder_type === "movie" && children.length === 0 && videos.length === 1;
}

/** 点击目录卡片的去向 */
export function folderTarget(node: FolderNode): MobileNavTarget {
  if (isSingleMovieNode(node)) {
    return { type: "detail", url: libraryDetailUrl(node.videos[0].file_path) };
  }
  return { type: "library", url: libraryUrl(node.path) };
}

/** 点击视频条目的去向。矩阵明确：进详情，不直接播放 */
export function videoTarget(video: VideoInfo): MobileNavTarget {
  return { type: "detail", url: libraryDetailUrl(video.file_path) };
}

function sortedVideos(videos: VideoInfo[]): VideoInfo[] {
  return [...(videos || [])].sort((a, b) => naturalCompare(a.file_name || "", b.file_name || ""));
}

const CN_DIGITS: Record<string, number> = {
  零: 0, 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9,
};

/** "十二" → 12、"十" → 10、"三" → 3。季号不会大到需要通用中文数字解析器 */
function parseCnNumber(text: string): number | null {
  if (!text) return null;
  const tenIdx = text.indexOf("十");
  if (tenIdx < 0) {
    const single = CN_DIGITS[text];
    return single === undefined ? null : single;
  }
  const highPart = text.slice(0, tenIdx);
  const lowPart = text.slice(tenIdx + 1);
  const high = highPart ? CN_DIGITS[highPart] : 1;
  const low = lowPart ? CN_DIGITS[lowPart] : 0;
  if (high === undefined || low === undefined) return null;
  return high * 10 + low;
}

/**
 * 从季目录名里取季号。
 *
 * 必须按季号排而不是按显示名排：季的 `clean_name` 是后端算出来的
 * "三体 第一季" / "三体 第二季"，`localeCompare` 对中文数字给不出正确顺序
 * （"一" 和 "二" 的排序与数值无关），第二季会排到第一季前面。
 */
export function seasonNumber(name: string): number | null {
  if (!name) return null;
  const arabic = name.match(/(?:season|s)\s*(\d{1,3})\b/i) || name.match(/第\s*(\d{1,3})\s*[季部]/);
  if (arabic) return Number(arabic[1]);
  const cn = name.match(/第\s*([零一二三四五六七八九十]{1,3})\s*[季部]/);
  if (cn) return parseCnNumber(cn[1]);
  return null;
}

/**
 * 从集文件名里取季号，如 "三体 S01E05.mkv" → 1。
 *
 * 不能用 `seasonNumber()`：它要求季号后面是词边界，而 `S01E05` 里数字紧跟字母，
 * 边界不成立。这两个场景的输入形状不同，各用各的正则。
 */
export function episodeSeasonNumber(fileName: string): number | null {
  const match = (fileName || "").match(/S(\d{1,3})E\d{1,4}/i);
  return match ? Number(match[1]) : null;
}

/** 从集文件名里取集号，如 "三体 S01E05.mkv" → 5。用于详情页与播放页的定位标签 */
export function episodeNumber(fileName: string): number | null {
  const match = (fileName || "").match(/S\d{1,3}E(\d{1,4})/i);
  return match ? Number(match[1]) : null;
}

/** 普通目录排序：按显示名自然序 */
function sortedFolders(children: FolderNode[]): FolderNode[] {
  return [...(children || [])].sort((a, b) => naturalCompare(nodeDisplayName(a), nodeDisplayName(b)));
}

/** 季排序：优先季号；取不到季号的（如 "特别篇"）排在有季号的后面 */
function sortedSeasons(children: FolderNode[]): FolderNode[] {
  return [...(children || [])].sort((a, b) => {
    const an = seasonNumber(a.name) ?? seasonNumber(nodeDisplayName(a));
    const bn = seasonNumber(b.name) ?? seasonNumber(nodeDisplayName(b));
    if (an !== null && bn !== null && an !== bn) return an - bn;
    if (an !== null && bn === null) return -1;
    if (an === null && bn !== null) return 1;
    return naturalCompare(nodeDisplayName(a), nodeDisplayName(b));
  });
}

/** 季节点：tv 的 children 里带视频的那些。空季目录不展示，点进去只有空屏 */
function seasonNodes(node: FolderNode): FolderNode[] {
  return sortedSeasons((node.children || []).filter(c => (c.video_count || 0) > 0));
}

/**
 * 把节点翻译成一屏视图。覆盖 TODO §六 的十行矩阵：
 *
 * | 节点 | 结果 |
 * |---|---|
 * | 根 / 虚拟库 / 普通非叶子 / mixed | folders |
 * | TV 多季 | seasons |
 * | TV 单季 | episodes（该季的集），副标题带季名 |
 * | 扁平 TV（无季目录） | episodes（直属集） |
 * | season 节点 | episodes |
 * | movie / 普通叶子 | episodes（通常一条） |
 * | collection / series | folders +（自己有直属视频时）videos 两段同屏 |
 */
export function resolveLibraryView(node: FolderNode): MobileLibraryView {
  const title = nodeDisplayName(node);
  const ownVideos = sortedVideos(node.videos || []);

  if (node.folder_type === "tv") {
    const seasons = seasonNodes(node);
    if (seasons.length >= 2) {
      // ownVideos 不能丢：`Season 1/` 旁边放 `剧场版.mkv`、`SP01.mkv` 是常见布局，
      // 这些文件留在 tv 节点自己的 videos 里。丢掉它们在移动端就彻底不可达。
      return {
        kind: "seasons",
        folders: seasons,
        videos: [],
        extraVideos: ownVideos,
        title,
        subtitle: "",
        isEmpty: false,
      };
    }
    if (seasons.length === 1) {
      // 单季不该逼用户多点一层。直接摊开该季的集，季名放副标题。
      // 剧目录下的散片走 extraVideos 单独一段，不和正片共用集号。
      const only = seasons[0];
      const seasonVideos = sortedVideos(only.videos || []);
      return {
        kind: "episodes",
        folders: sortedFolders(only.children || []),
        videos: seasonVideos,
        extraVideos: ownVideos,
        title,
        subtitle: nodeDisplayName(only),
        isEmpty:
          seasonVideos.length === 0
          && ownVideos.length === 0
          && (only.children || []).length === 0,
      };
    }
    // 扁平剧：集直接挂在剧目录下
    return {
      kind: "episodes",
      folders: [],
      videos: ownVideos,
      extraVideos: [],
      title,
      subtitle: "",
      isEmpty: ownVideos.length === 0,
    };
  }

  const folders = sortedFolders(node.children || []);
  if (folders.length === 0) {
    return {
      kind: "episodes",
      folders: [],
      videos: ownVideos,
      extraVideos: [],
      title,
      subtitle: "",
      isEmpty: ownVideos.length === 0,
    };
  }

  // collection / series / mixed / 普通非叶子：子目录与直属视频同屏，
  // 不然"自己也有视频"的 collection 会漏掉那几个文件
  return {
    kind: "folders",
    folders,
    videos: ownVideos,
    extraVideos: [],
    title,
    subtitle: "",
    isEmpty: false,
  };
}
