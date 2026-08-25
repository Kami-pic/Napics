// `/library/tree` 的契约夹具。
//
// 字段和层级按后端 backend/routes/library_tree.py 实际产出的形状写，
// **不许简化成理想模型** —— 简化过的夹具测不出"季是父节点强行改写出来的"
// 和"collection 自己也可能带直属视频"这两个真实结构。
import type { FolderNode, VideoInfo } from "@/types";

const MEDIA_ROOT = "D:\\影视";

export function makeVideo(overrides: Partial<VideoInfo> & { file_path: string }): VideoInfo {
  const fileName = overrides.file_name ?? overrides.file_path.split("\\").pop() ?? "";
  return {
    file_name: fileName,
    folder_name: "",
    size_gb: 12.4,
    resolution: "2160p",
    width: 3840,
    height: 2160,
    codec: "hevc",
    container: "mkv",
    duration_min: 126,
    audio_codec: "eac3",
    subtitle_count: 2,
    subtitle_text_count: 2,
    subtitle_graphic_count: 0,
    hdr_type: "HDR10",
    is_low_res: false,
    has_poster: true,
    has_nfo: true,
    organize_status: "ok",
    ...overrides,
  };
}

export function makeNode(overrides: Partial<FolderNode> & { name: string; path: string }): FolderNode {
  const videos = overrides.videos ?? [];
  const children = overrides.children ?? [];
  const ownCount = videos.length + children.reduce((sum, c) => sum + (c.video_count || 0), 0);
  return {
    children,
    videos,
    video_count: overrides.video_count ?? ownCount,
    has_cover: ownCount > 0,
    is_category: false,
    is_top_category: false,
    is_virtual_library: false,
    parent_category_tag: "",
    folder_type: "",
    shadow_name: "",
    clean_name: overrides.clean_name ?? overrides.name,
    clean_name_cn: "",
    clean_name_en: "",
    clean_name_original: "",
    category_tag: "",
    ...overrides,
  };
}

// ── 电影侧 ──

export const MOVIE_NODE = makeNode({
  name: "钢铁侠 Iron Man (2008)",
  path: `${MEDIA_ROOT}\\电影\\钢铁侠 Iron Man (2008)`,
  folder_type: "movie",
  parent_category_tag: "movie",
  clean_name: "钢铁侠",
  clean_name_cn: "钢铁侠",
  clean_name_en: "Iron Man",
  videos: [
    makeVideo({
      file_path: `${MEDIA_ROOT}\\电影\\钢铁侠 Iron Man (2008)\\钢铁侠 Iron Man (2008).mkv`,
      folder_name: "电影/钢铁侠 Iron Man (2008)",
      clean_name: "钢铁侠",
      clean_name_cn: "钢铁侠",
      clean_name_en: "Iron Man",
    }),
  ],
});

/** series：三部曲，children 各是单视频目录 */
export const SERIES_NODE = makeNode({
  name: "指环王三部曲",
  path: `${MEDIA_ROOT}\\电影\\指环王三部曲`,
  folder_type: "series",
  parent_category_tag: "movie",
  children: [
    makeNode({
      name: "指环王1 护戒使者 (2001)",
      path: `${MEDIA_ROOT}\\电影\\指环王三部曲\\指环王1 护戒使者 (2001)`,
      folder_type: "movie",
      videos: [makeVideo({ file_path: `${MEDIA_ROOT}\\电影\\指环王三部曲\\指环王1 护戒使者 (2001)\\指环王1.mkv` })],
    }),
    makeNode({
      name: "指环王10 完全虚构版 (2010)",
      path: `${MEDIA_ROOT}\\电影\\指环王三部曲\\指环王10 完全虚构版 (2010)`,
      folder_type: "movie",
      videos: [makeVideo({ file_path: `${MEDIA_ROOT}\\电影\\指环王三部曲\\指环王10 完全虚构版 (2010)\\指环王10.mkv` })],
    }),
    makeNode({
      name: "指环王2 双塔奇兵 (2002)",
      path: `${MEDIA_ROOT}\\电影\\指环王三部曲\\指环王2 双塔奇兵 (2002)`,
      folder_type: "movie",
      videos: [makeVideo({ file_path: `${MEDIA_ROOT}\\电影\\指环王三部曲\\指环王2 双塔奇兵 (2002)\\指环王2.mkv` })],
    }),
  ],
});

/** collection：既有子目录，**自己也有直属视频**。这一条是最容易被漏掉的形态 */
export const COLLECTION_NODE = makeNode({
  name: "漫威合集",
  path: `${MEDIA_ROOT}\\电影\\漫威合集`,
  folder_type: "collection",
  parent_category_tag: "movie",
  children: [
    makeNode({
      name: "美国队长 (2011)",
      path: `${MEDIA_ROOT}\\电影\\漫威合集\\美国队长 (2011)`,
      folder_type: "movie",
      videos: [makeVideo({ file_path: `${MEDIA_ROOT}\\电影\\漫威合集\\美国队长 (2011)\\美国队长.mkv` })],
    }),
  ],
  videos: [
    makeVideo({
      file_path: `${MEDIA_ROOT}\\电影\\漫威合集\\雷神 Thor (2011).mkv`,
      file_name: "雷神 Thor (2011).mkv",
    }),
  ],
});

// ── 剧集侧 ──

/** TV 多季。季节点的 folder_type 是父节点 post_process 改写出来的 */
export const TV_MULTI_SEASON_NODE = makeNode({
  name: "三体 (2023)",
  path: `${MEDIA_ROOT}\\剧集\\三体 (2023)`,
  folder_type: "tv",
  parent_category_tag: "tv",
  clean_name: "三体",
  children: [
    makeNode({
      name: "Season 2",
      path: `${MEDIA_ROOT}\\剧集\\三体 (2023)\\Season 2`,
      folder_type: "season",
      clean_name: "三体 第二季",
      videos: [
        makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\三体 (2023)\\Season 2\\三体 S02E01.mkv`, file_name: "三体 S02E01.mkv" }),
      ],
    }),
    makeNode({
      name: "Season 1",
      path: `${MEDIA_ROOT}\\剧集\\三体 (2023)\\Season 1`,
      folder_type: "season",
      clean_name: "三体 第一季",
      videos: [
        makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\三体 (2023)\\Season 1\\三体 S01E10.mkv`, file_name: "三体 S01E10.mkv" }),
        makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\三体 (2023)\\Season 1\\三体 S01E02.mkv`, file_name: "三体 S01E02.mkv" }),
        makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\三体 (2023)\\Season 1\\三体 S01E01.mkv`, file_name: "三体 S01E01.mkv" }),
      ],
    }),
  ],
});

/** TV 单季：只有一个季目录 */
export const TV_SINGLE_SEASON_NODE = makeNode({
  name: "沙丘：预言 (2024)",
  path: `${MEDIA_ROOT}\\剧集\\沙丘：预言 (2024)`,
  folder_type: "tv",
  parent_category_tag: "tv",
  children: [
    makeNode({
      name: "Season 1",
      path: `${MEDIA_ROOT}\\剧集\\沙丘：预言 (2024)\\Season 1`,
      folder_type: "season",
      clean_name: "沙丘：预言 第一季",
      videos: [
        makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\沙丘：预言 (2024)\\Season 1\\S01E02.mkv`, file_name: "S01E02.mkv" }),
        makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\沙丘：预言 (2024)\\Season 1\\S01E01.mkv`, file_name: "S01E01.mkv" }),
      ],
    }),
  ],
});

/** 扁平 TV：没有季目录，集直接挂在剧目录下 */
export const TV_FLAT_NODE = makeNode({
  name: "老友记 Friends",
  path: `${MEDIA_ROOT}\\剧集\\老友记 Friends`,
  folder_type: "tv",
  parent_category_tag: "tv",
  videos: [
    makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\老友记 Friends\\Friends E10.mkv`, file_name: "Friends E10.mkv" }),
    makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\老友记 Friends\\Friends E2.mkv`, file_name: "Friends E2.mkv" }),
    makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\老友记 Friends\\Friends E1.mkv`, file_name: "Friends E1.mkv" }),
  ],
});

/** 季目录存在但一条视频都没入库（扫描中断留下的空壳） */
export const TV_EMPTY_SEASON_NODE = makeNode({
  name: "空壳剧 (2025)",
  path: `${MEDIA_ROOT}\\剧集\\空壳剧 (2025)`,
  folder_type: "tv",
  parent_category_tag: "tv",
  children: [
    makeNode({
      name: "Season 1",
      path: `${MEDIA_ROOT}\\剧集\\空壳剧 (2025)\\Season 1`,
      folder_type: "season",
      video_count: 0,
    }),
  ],
  video_count: 0,
});

/** mixed：一个目录里塞了多部各带子目录的剧 */
export const MIXED_NODE = makeNode({
  name: "杂项",
  path: `${MEDIA_ROOT}\\剧集\\杂项`,
  folder_type: "mixed",
  parent_category_tag: "tv",
  children: [TV_MULTI_SEASON_NODE, TV_FLAT_NODE],
});

/** 普通叶子目录：没有 folder_type，只有几个视频 */
export const PLAIN_LEAF_NODE = makeNode({
  name: "未分类",
  path: `${MEDIA_ROOT}\\未分类`,
  videos: [
    makeVideo({ file_path: `${MEDIA_ROOT}\\未分类\\b.mkv`, file_name: "b.mkv" }),
    makeVideo({ file_path: `${MEDIA_ROOT}\\未分类\\a.mkv`, file_name: "a.mkv" }),
  ],
});

/** 一级分类节点（虚拟库） */
export const TV_LIBRARY_NODE = makeNode({
  name: "剧集",
  path: "E:\\剧集库",
  folder_type: "mixed",
  is_top_category: true,
  is_virtual_library: true,
  category_tag: "tv",
  children: [TV_MULTI_SEASON_NODE, TV_SINGLE_SEASON_NODE, TV_FLAT_NODE, TV_EMPTY_SEASON_NODE, MIXED_NODE],
});

export const MOVIE_LIBRARY_NODE = makeNode({
  name: "电影",
  path: `${MEDIA_ROOT}\\电影`,
  folder_type: "mixed",
  is_top_category: true,
  category_tag: "movie",
  children: [MOVIE_NODE, SERIES_NODE, COLLECTION_NODE],
});

/** 根节点：name 固定是"媒体库"，path 是空串 */
export const LIBRARY_TREE = makeNode({
  name: "媒体库",
  path: "",
  clean_name: "媒体库",
  children: [MOVIE_LIBRARY_NODE, TV_LIBRARY_NODE, PLAIN_LEAF_NODE],
});

/**
 * 多季剧 + 剧目录下的直属剧场版。
 *
 * `Season 1/` 旁边躺着 `剧场版.mkv` 是真实常见布局（library_tree.py 会把它留在
 * tv 节点自己的 videos 里）。丢掉这一段，文件在移动端就完全不可达。
 */
export const TV_WITH_EXTRAS_NODE = makeNode({
  name: "进击的巨人",
  path: `${MEDIA_ROOT}\\剧集\\进击的巨人`,
  folder_type: "tv",
  parent_category_tag: "tv",
  children: [
    makeNode({
      name: "Season 1",
      path: `${MEDIA_ROOT}\\剧集\\进击的巨人\\Season 1`,
      folder_type: "season",
      videos: [makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\进击的巨人\\Season 1\\S01E01.mkv`, file_name: "S01E01.mkv" })],
    }),
    makeNode({
      name: "Season 2",
      path: `${MEDIA_ROOT}\\剧集\\进击的巨人\\Season 2`,
      folder_type: "season",
      videos: [makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\进击的巨人\\Season 2\\S02E01.mkv`, file_name: "S02E01.mkv" })],
    }),
  ],
  videos: [
    makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\进击的巨人\\剧场版 咆哮.mkv`, file_name: "剧场版 咆哮.mkv" }),
  ],
});

/** 单季剧 + 剧目录下的 SP */
export const TV_SINGLE_SEASON_WITH_SP_NODE = makeNode({
  name: "孤独摇滚",
  path: `${MEDIA_ROOT}\\剧集\\孤独摇滚`,
  folder_type: "tv",
  parent_category_tag: "tv",
  children: [
    makeNode({
      name: "Season 1",
      path: `${MEDIA_ROOT}\\剧集\\孤独摇滚\\Season 1`,
      folder_type: "season",
      clean_name: "孤独摇滚 第一季",
      videos: [
        makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\孤独摇滚\\Season 1\\S01E02.mkv`, file_name: "S01E02.mkv" }),
        makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\孤独摇滚\\Season 1\\S01E01.mkv`, file_name: "S01E01.mkv" }),
      ],
    }),
  ],
  videos: [
    makeVideo({ file_path: `${MEDIA_ROOT}\\剧集\\孤独摇滚\\SP 特别篇.mkv`, file_name: "SP 特别篇.mkv" }),
  ],
});
