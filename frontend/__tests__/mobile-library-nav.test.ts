// 媒体库导航域：TODO §六 行为矩阵逐行断言。
//
// 夹具是 __tests__/helpers/libraryTreeFixture.ts，按后端真实产出的字段与层级写，
// 不是简化模型。
import { describe, it, expect } from "vitest";
import {
  findNode,
  findParentPath,
  resolveLibraryView,
  folderTarget,
  videoTarget,
  isSingleMovieNode,
  nodeDisplayName,
  videoDisplayName,
  seasonNumber,
} from "@/lib/mobile/libraryNav";
import { libraryUrl, libraryDetailUrl, parsePathParam } from "@/lib/mobile/mobileRouteUtils";
import {
  LIBRARY_TREE,
  MOVIE_NODE,
  SERIES_NODE,
  COLLECTION_NODE,
  TV_MULTI_SEASON_NODE,
  TV_SINGLE_SEASON_NODE,
  TV_FLAT_NODE,
  TV_EMPTY_SEASON_NODE,
  MIXED_NODE,
  PLAIN_LEAF_NODE,
  TV_LIBRARY_NODE,
} from "./helpers/libraryTreeFixture";

describe("findNode", () => {
  it("空 path 返回根节点（根的 path 就是空串）", () => {
    expect(findNode(LIBRARY_TREE, "")).toBe(LIBRARY_TREE);
  });

  it("能找到第三层的季节点，说明真的做了全树遍历", () => {
    const season = findNode(LIBRARY_TREE, TV_MULTI_SEASON_NODE.children[1].path);
    expect(season?.name).toBe("Season 1");
    expect(season?.folder_type).toBe("season");
  });

  it("不存在的 path 返回 null，页面据此显示明确错误而不是白屏", () => {
    expect(findNode(LIBRARY_TREE, "D:\\不存在\\目录")).toBeNull();
  });

  it("树还没加载时返回 null，不抛异常", () => {
    expect(findNode(null, "D:\\影视")).toBeNull();
  });

  it("findParentPath 给出返回键的 fallback 目标", () => {
    const season = TV_MULTI_SEASON_NODE.children[1];
    expect(findParentPath(LIBRARY_TREE, season.path)).toBe(TV_MULTI_SEASON_NODE.path);
    // 一级分类的父是根，根的 path 是空串 —— 空串是合法结果，不等于"没有父"
    expect(findParentPath(LIBRARY_TREE, TV_LIBRARY_NODE.path)).toBe("");
    // 根自己没有父
    expect(findParentPath(LIBRARY_TREE, "")).toBeNull();
    expect(findParentPath(LIBRARY_TREE, "D:\\不存在")).toBeNull();
  });

  it("Windows 路径原样匹配，不做归一化（树里的 path 和 query 里的 path 同源）", () => {
    const url = libraryUrl(MOVIE_NODE.path);
    const roundTripped = parsePathParam(new URL(url, "http://x").searchParams);
    expect(roundTripped).toBe(MOVIE_NODE.path);
    expect(findNode(LIBRARY_TREE, roundTripped)).toBe(MOVIE_NODE);
  });
});

describe("行为矩阵：一屏显示什么", () => {
  it("根节点 → 一级分类卡片", () => {
    const view = resolveLibraryView(LIBRARY_TREE);
    expect(view.kind).toBe("folders");
    expect(view.folders.map(f => f.name)).toEqual(["电影", "剧集", "未分类"].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" })));
    expect(view.isEmpty).toBe(false);
  });

  it("虚拟库 → 进入后按剧目呈现，仍是目录卡片", () => {
    const view = resolveLibraryView(TV_LIBRARY_NODE);
    expect(view.kind).toBe("folders");
    expect(view.folders.length).toBe(5);
  });

  it("TV 多季 → 季列表", () => {
    const view = resolveLibraryView(TV_MULTI_SEASON_NODE);
    expect(view.kind).toBe("seasons");
    expect(view.folders.map(f => f.name)).toEqual(["Season 1", "Season 2"]);
    expect(view.videos).toEqual([]);
    expect(view.title).toBe("三体");
  });

  it("TV 单季 → 直接是集列表，页头保留剧名与季名", () => {
    const view = resolveLibraryView(TV_SINGLE_SEASON_NODE);
    expect(view.kind).toBe("episodes");
    expect(view.title).toBe("沙丘：预言 (2024)");
    expect(view.subtitle).toBe("沙丘：预言 第一季");
    expect(view.videos.map(v => v.file_name)).toEqual(["S01E01.mkv", "S01E02.mkv"]);
  });

  it("扁平 TV → 直属集列表，且按集号自然序（E2 在 E10 前）", () => {
    const view = resolveLibraryView(TV_FLAT_NODE);
    expect(view.kind).toBe("episodes");
    expect(view.folders).toEqual([]);
    expect(view.videos.map(v => v.file_name)).toEqual([
      "Friends E1.mkv",
      "Friends E2.mkv",
      "Friends E10.mkv",
    ]);
  });

  it("季节点本身 → 集列表", () => {
    const season = TV_MULTI_SEASON_NODE.children[1];
    const view = resolveLibraryView(season);
    expect(view.kind).toBe("episodes");
    expect(view.videos.map(v => v.file_name)).toEqual([
      "三体 S01E01.mkv",
      "三体 S01E02.mkv",
      "三体 S01E10.mkv",
    ]);
  });

  it("季目录全空的剧 → 空态，不是白屏", () => {
    const view = resolveLibraryView(TV_EMPTY_SEASON_NODE);
    expect(view.isEmpty).toBe(true);
    expect(view.videos).toEqual([]);
    expect(view.folders).toEqual([]);
  });

  it("collection 自己也有直属视频时两段同屏，不许漏掉那几个文件", () => {
    const view = resolveLibraryView(COLLECTION_NODE);
    expect(view.kind).toBe("folders");
    expect(view.folders.map(f => f.name)).toEqual(["美国队长 (2011)"]);
    expect(view.videos.map(v => v.file_name)).toEqual(["雷神 Thor (2011).mkv"]);
  });

  it("series → 子项目，且 10 排在 2 之后", () => {
    const view = resolveLibraryView(SERIES_NODE);
    expect(view.kind).toBe("folders");
    expect(view.folders.map(f => f.name)).toEqual([
      "指环王1 护戒使者 (2001)",
      "指环王2 双塔奇兵 (2002)",
      "指环王10 完全虚构版 (2010)",
    ]);
  });

  it("mixed → 子目录卡片，不误判成季列表", () => {
    const view = resolveLibraryView(MIXED_NODE);
    expect(view.kind).toBe("folders");
    expect(view.folders.length).toBe(2);
  });

  it("普通叶子目录 → 直属视频列表", () => {
    const view = resolveLibraryView(PLAIN_LEAF_NODE);
    expect(view.kind).toBe("episodes");
    expect(view.videos.map(v => v.file_name)).toEqual(["a.mkv", "b.mkv"]);
  });

  it("单电影节点即使被直接访问也有内容，不是空屏", () => {
    const view = resolveLibraryView(MOVIE_NODE);
    expect(view.kind).toBe("episodes");
    expect(view.videos.length).toBe(1);
    expect(view.isEmpty).toBe(false);
  });
});

describe("行为矩阵：点了去哪", () => {
  it("单电影卡片 → 视频详情，不是再下钻一层", () => {
    expect(isSingleMovieNode(MOVIE_NODE)).toBe(true);
    expect(folderTarget(MOVIE_NODE)).toEqual({
      type: "detail",
      url: libraryDetailUrl(MOVIE_NODE.videos[0].file_path),
    });
  });

  it("folder_type 是 movie 但塞了多个文件 → 仍然下钻，不能只看 folder_type", () => {
    const fake = { ...PLAIN_LEAF_NODE, folder_type: "movie" };
    expect(isSingleMovieNode(fake)).toBe(false);
    expect(folderTarget(fake).type).toBe("library");
  });

  it("剧 / 季 / collection / series 卡片 → 下钻列表页", () => {
    for (const node of [TV_MULTI_SEASON_NODE, TV_MULTI_SEASON_NODE.children[0], COLLECTION_NODE, SERIES_NODE]) {
      expect(folderTarget(node)).toEqual({ type: "library", url: libraryUrl(node.path) });
    }
  });

  it("视频条目 → 详情，不直接播放", () => {
    const video = TV_FLAT_NODE.videos[0];
    expect(videoTarget(video)).toEqual({ type: "detail", url: libraryDetailUrl(video.file_path) });
    expect(videoTarget(video).url).not.toContain("/m/play");
  });
});

describe("季号解析（决定季列表顺序）", () => {
  it("阿拉伯数字的三种写法", () => {
    expect(seasonNumber("Season 2")).toBe(2);
    expect(seasonNumber("S03")).toBe(3);
    expect(seasonNumber("第 12 季")).toBe(12);
  });

  it("中文数字：localeCompare 排不对的正是这一类", () => {
    expect(seasonNumber("三体 第一季")).toBe(1);
    expect(seasonNumber("三体 第二季")).toBe(2);
    expect(seasonNumber("第十季")).toBe(10);
    expect(seasonNumber("第十二季")).toBe(12);
    expect(seasonNumber("第二十季")).toBe(20);
  });

  it("取不到季号返回 null（特别篇之类）", () => {
    expect(seasonNumber("Specials")).toBeNull();
    expect(seasonNumber("特别篇")).toBeNull();
    expect(seasonNumber("")).toBeNull();
  });

  it("中文季名的季列表按季号排，不按字面", () => {
    const cnSeasons = {
      ...TV_MULTI_SEASON_NODE,
      children: [
        { ...TV_MULTI_SEASON_NODE.children[0], name: "第二季", clean_name: "三体 第二季" },
        { ...TV_MULTI_SEASON_NODE.children[1], name: "第一季", clean_name: "三体 第一季" },
      ],
    };
    expect(resolveLibraryView(cnSeasons).folders.map(f => f.name)).toEqual(["第一季", "第二季"]);
  });

  it("没有季号的季目录排在有季号的后面", () => {
    const withSpecials = {
      ...TV_MULTI_SEASON_NODE,
      children: [
        { ...TV_MULTI_SEASON_NODE.children[0], name: "Specials", clean_name: "特别篇" },
        TV_MULTI_SEASON_NODE.children[1],
      ],
    };
    expect(resolveLibraryView(withSpecials).folders.map(f => f.name)).toEqual(["Season 1", "Specials"]);
  });
});

describe("显示名", () => {
  it("优先清洗名，清洗名为空串时回退原名（不能用 ??）", () => {
    expect(nodeDisplayName(TV_MULTI_SEASON_NODE)).toBe("三体");
    expect(nodeDisplayName({ ...TV_MULTI_SEASON_NODE, clean_name: "" })).toBe("三体 (2023)");
    expect(videoDisplayName(MOVIE_NODE.videos[0])).toBe("钢铁侠");
    expect(videoDisplayName({ ...MOVIE_NODE.videos[0], clean_name: "" })).toBe("钢铁侠 Iron Man (2008).mkv");
  });
});
