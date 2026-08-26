// 卡片上显示什么：标题、副信息、徽标、标签、封面取址。
//
// **口径对齐桌面 `components/media/CardGrid.tsx`**（同一批数据两端读出来的数字必须一样）：
// - 叶子目录左上角是 `N 集`，series / collection 是 `N 部`，虚拟库是分类标签；
// - 右上角是「低画质」与 HDR 类型；
// - movie 目录与视频的副信息是 `分辨率 · 大小`，容器目录是 `N 个项目`。
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
  tone: "warning" | "hdr";
}

export interface MobileCardMeta {
  title: string;
  /** 一行副信息，拿不到任何字段时是空串（不显示占位） */
  subtitle: string;
  /** 取本地封面用的路径 */
  posterPath: string;
  /** 聚合容器要用子项封面（后端 `?cover=true`），刮削单元用自己的 poster.jpg */
  cover: boolean;
  badge?: { text: string; tone: MobileCardBadgeTone };
  tags: MobileCardTag[];
}

/** 视频的质量标签，目录卡与视频卡共用 */
function videoTags(video: VideoInfo | undefined): MobileCardTag[] {
  if (!video) return [];
  const tags: MobileCardTag[] = [];
  if (video.is_low_res) tags.push({ text: "低画质", tone: "warning" });
  if (video.hdr_type && video.hdr_type !== "SDR") tags.push({ text: video.hdr_type, tone: "hdr" });
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
    tags: videoTags(video),
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
      subtitle: `${node.video_count} 个视频`,
      cover: true,
      badge: { text: `${count} 部`, tone: type === "series" ? "series" : "collection" },
    };
  }

  if (type === "tv") {
    const seasons = children.filter(c => (c.video_count || 0) > 0).length;
    return {
      ...base,
      subtitle: "",
      cover: false,
      badge: {
        text: seasons > 1 ? `${seasons} 季 · ${node.video_count} 集` : `${node.video_count} 集`,
        tone: "episodes",
      },
    };
  }

  // 叶子目录（没有子目录但有视频）：徽标给集数，和桌面的 `N 集` 一致
  if (children.length === 0 && videos.length > 0) {
    return {
      ...base,
      subtitle: "",
      cover: false,
      badge: { text: `${node.video_count} 集`, tone: "episodes" },
    };
  }

  // 其余容器目录（mixed / 无类型的分类目录）
  return {
    ...base,
    subtitle: `${node.video_count} 个视频`,
    cover: true,
  };
}
