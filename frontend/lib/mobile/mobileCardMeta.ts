// 卡片上显示什么：标题、副信息、徽标、标签、封面取址。
//
// **口径对齐桌面 `components/media/CardGrid.tsx`**（同一批数据两端读出来的数字必须一样）：
// - 左上角：叶子目录 `N 集`、series / collection `N 部`、tv `N 季 · N 集`、
//   虚拟库与顶级分类目录是分类标签；
// - 右上角：低画质、HDR 类型；
// - 底部副信息：movie 目录与视频是 `分辨率 · 大小`，容器目录是 `N 个项目`；
// - 视频还有两个状态标记：未整理（灰点）、识别失败（⚠）。
//
// 这里只做纯计算，不碰 DOM，也不决定点击去向（那在 libraryNav）。
import type { FolderNode, VideoInfo } from "@/types";
import { getCategoryTagLabel } from "@/lib/folderTypes";
import { formatSize } from "@/lib/utils";
import { nodeDisplayName, seasonNumber, videoDisplayName } from "./libraryNav";

/** 徽标语义。视图层各自映射到 --m-* 变量，这里不写颜色 */
export type MobileCardBadgeTone = "episodes" | "series" | "collection" | "library";

export interface MobileCardTag {
  text: string;
  /** warning=低画质、hdr=HDR 类型、muted=未整理、danger=识别失败 */
  tone: "warning" | "hdr" | "muted" | "danger";
}

export interface MobileCardMeta {
  title: string;
  /** 一行副信息，拿不到任何字段时是空串（不显示占位） */
  subtitle: string;
  /** 取本地封面用的路径 */
  posterPath: string;
  /**
   * 聚合容器要传 `?cover=true`。后端在这个模式下找的是容器自己的 `cover.jpg`，
   * **不会**回退到子项封面 —— 所以聚合容器没有 cover.jpg 时就是占位图。
   */
  cover: boolean;
  badge?: { text: string; tone: MobileCardBadgeTone };
  tags: MobileCardTag[];
}

/** 视频的质量与状态标签，目录卡与视频卡共用。顺序与桌面一致（质量在前） */
function videoTags(video: VideoInfo | undefined, withStatus = false): MobileCardTag[] {
  if (!video) return [];
  const tags: MobileCardTag[] = [];
  if (video.is_low_res) tags.push({ text: "低画质", tone: "warning" });
  if (video.hdr_type && video.hdr_type !== "SDR") tags.push({ text: video.hdr_type, tone: "hdr" });
  if (withStatus) {
    // 桌面在视频卡标题前放一个灰点表示"未整理"、⚠ 表示"识别失败"。
    // 这两条是整库最有用的筛查信息，移动端不能丢。
    if (!video.shadow_name && !video.organize_status) tags.push({ text: "未整理", tone: "muted" });
    if (video.organize_status === "scrape_failed") tags.push({ text: "识别失败", tone: "danger" });
  }
  return tags;
}

function specLine(video: VideoInfo | undefined): string {
  if (!video) return "";
  const parts = [video.resolution, formatSize(video.size_gb)].filter(Boolean);
  return parts.join(" · ");
}

export function videoCardMeta(video: VideoInfo): MobileCardMeta {
  return {
    title: videoDisplayName(video),
    subtitle: specLine(video),
    posterPath: video.file_path,
    cover: false,
    tags: videoTags(video, true),
  };
}

/** 季卡片：徽标带季号 + 集数。季号比目录名更好认（目录名可能是 `Season 1` 也可能是中文） */
export function seasonCardMeta(node: FolderNode): MobileCardMeta {
  const num = seasonNumber(node.name) ?? seasonNumber(nodeDisplayName(node));
  const label = num === null ? "" : `S${String(num).padStart(2, "0")}`;
  return {
    title: nodeDisplayName(node),
    subtitle: "",
    posterPath: node.path,
    cover: false,
    badge: {
      text: label ? `${label} · ${node.video_count} 集` : `${node.video_count} 集`,
      tone: "episodes",
    },
    tags: [],
  };
}

export function folderCardMeta(node: FolderNode): MobileCardMeta {
  const type = node.folder_type || "";
  const children = node.children || [];
  const videos = node.videos || [];
  const base = {
    title: nodeDisplayName(node),
    posterPath: node.path,
    tags: [] as MobileCardTag[],
  };

  // 虚拟媒体库：徽标是分类标签，副信息是项目数
  if (node.is_virtual_library) {
    return {
      ...base,
      subtitle: `${node.video_count} 个项目`,
      cover: true,
      badge: { text: getCategoryTagLabel(node.category_tag || ""), tone: "library" },
    };
  }

  // 单电影目录：显示这个文件的规格与质量标签，和桌面一致
  if (type === "movie" && videos.length > 0) {
    return {
      ...base,
      subtitle: specLine(videos[0]),
      cover: false,
      tags: videoTags(videos[0]),
    };
  }

  if (type === "series" || type === "collection") {
    const count = children.length || node.video_count;
    return {
      ...base,
      subtitle: `${node.video_count} 个项目`,
      cover: true,
      badge: { text: `${count} 部`, tone: type === "series" ? "series" : "collection" },
    };
  }

  if (type === "tv") {
    // 集数只累加季目录，和桌面 `item.seasons.reduce(...)` 一致。
    // 不能用 node.video_count —— 它是**递归总数**，把剧场版/SP 也算进去，
    // 于是两端同一部剧显示的集数会差几集。
    const seasons = children.filter(c => (c.video_count || 0) > 0);
    const episodes = seasons.reduce((sum, c) => sum + (c.video_count || 0), 0);
    return {
      ...base,
      subtitle: "",
      cover: false,
      badge: {
        // 扁平剧（没有季目录）按桌面的口径算作一季
        text: seasons.length > 1
          ? `${seasons.length} 季 · ${episodes} 集`
          : `${episodes || node.video_count} 集`,
        tone: "episodes",
      },
    };
  }

  // 叶子目录（没有子目录但有视频）：徽标给集数。
  // `is_category` 例外与桌面一致 —— 一堆互不相关电影的分类目录标「N 集」是错的
  if (children.length === 0 && videos.length > 0 && !node.is_category) {
    return {
      ...base,
      subtitle: "",
      cover: false,
      badge: { text: `${node.video_count} 集`, tone: "episodes" },
    };
  }

  // 其余容器目录（mixed / 分类目录）。
  //
  // 桌面对 `category_tag` 非空的目录会额外渲染一个可点的分类徽标（点了能改分类）。
  // 移动端**刻意不加**：这类目录的名字往往就是分类名本身（顶级「电影」目录的
  // category_tag 就是 movie → 徽标写「电影」），标题旁边再挂一个同样的词，
  // 在 ~104px 宽的卡片上纯属浪费；而移动端也不提供改分类的操作，徽标点不动。
  return {
    ...base,
    subtitle: `${node.video_count} 个项目`,
    cover: true,
  };
}
