// buildCardItems 的卡片聚合规则 — 这段逻辑由桌面 CardGrid 与移动端共用，
// 从 CardGrid.tsx 抽出时无测试覆盖，此处锁住行为
import { describe, it, expect } from "vitest";
import { buildCardItems } from "@/components/media/cardGridUtils";
import type { FolderNode, VideoInfo } from "@/types";

function makeFolder(overrides: Partial<FolderNode> = {}): FolderNode {
  return {
    name: "文件夹", path: "/lib/文件夹", children: [], videos: [],
    video_count: 0, has_cover: false, ...overrides,
  };
}

function makeVideo(overrides: Partial<VideoInfo> = {}): VideoInfo {
  return {
    file_name: "a.mkv", file_path: "/lib/a.mkv", folder_name: "文件夹",
    size_gb: 1, resolution: "1080p", width: 1920, height: 1080,
    audio_codec: "AAC", subtitle_count: 0, hdr_type: "SDR", is_low_res: false,
    ...overrides,
  };
}

describe("buildCardItems — 空输入", () => {
  it("currentFolder 为 null 时返回空数组", () => {
    expect(buildCardItems(null, {})).toEqual([]);
  });
});

describe("buildCardItems — 虚拟媒体库自身作为内容项", () => {
  it("tv 且有子目录：聚成单张 tv 卡片，季按季号排序，parentNode 指向自身", () => {
    const s2 = makeFolder({ name: "第二季", path: "/lib/剧/S2" });
    const s1 = makeFolder({ name: "第一季", path: "/lib/剧/S1" });
    const lib = makeFolder({
      name: "剧", path: "/lib/剧", is_virtual_library: true,
      folder_type: "tv", children: [s2, s1],
    });

    const items = buildCardItems(lib, {});

    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ type: "tv", seriesName: "剧", id: "ms-/lib/剧" });
    const tv = items[0] as Extract<typeof items[0], { type: "tv" }>;
    expect(tv.seasons.map(s => s.name)).toEqual(["第一季", "第二季"]);
    expect(tv.parentNode).toBe(lib);
  });

  it("tv 但无子目录只有视频：季列表退化为自身", () => {
    const lib = makeFolder({
      name: "扁平剧", path: "/lib/扁平剧", is_virtual_library: true,
      folder_type: "tv", videos: [makeVideo()],
    });

    const items = buildCardItems(lib, {});

    const tv = items[0] as Extract<typeof items[0], { type: "tv" }>;
    expect(tv.type).toBe("tv");
    expect(tv.seasons).toEqual([lib]);
  });

  it("movie 且恰好一个视频：出 video 卡片而非文件夹卡片", () => {
    const v = makeVideo({ file_path: "/lib/片/x.mkv" });
    const lib = makeFolder({
      name: "片", path: "/lib/片", is_virtual_library: true,
      folder_type: "movie", videos: [v],
    });

    expect(buildCardItems(lib, {})).toEqual([
      { type: "video", data: v, id: "v-/lib/片/x.mkv-0" },
    ]);
  });

  it("collection 与 series 各自带 folder_type 前缀的 id", () => {
    const child = makeFolder({ name: "子", path: "/lib/合集/子" });
    const coll = makeFolder({
      name: "合集", path: "/lib/合集", is_virtual_library: true,
      folder_type: "collection", children: [child],
    });
    const series = makeFolder({
      name: "系列", path: "/lib/系列", is_virtual_library: true,
      folder_type: "series", children: [child],
    });

    expect(buildCardItems(coll, {})[0]).toMatchObject({ type: "collection", id: "collection-/lib/合集" });
    expect(buildCardItems(series, {})[0]).toMatchObject({ type: "series", id: "series-/lib/系列" });
  });

  it("其他 folder_type：回退为逐个子目录 + 视频", () => {
    const child = makeFolder({ name: "子", path: "/lib/杂/子" });
    const lib = makeFolder({
      name: "杂", path: "/lib/杂", is_virtual_library: true,
      folder_type: "mixed", children: [child],
    });
    const v = makeVideo({ file_path: "/lib/杂/v.mkv" });

    const items = buildCardItems(lib, { g: [v] });

    expect(items).toEqual([
      { type: "folder", data: child, id: "f-/lib/杂/子" },
      { type: "video", data: v, id: "v-/lib/杂/v.mkv-0" },
    ]);
  });
});

describe("buildCardItems — 普通目录下按 folder_type 分派", () => {
  it("series / collection 子目录各自成卡片", () => {
    const series = makeFolder({ name: "S", path: "/lib/S", folder_type: "series" });
    const coll = makeFolder({ name: "C", path: "/lib/C", folder_type: "collection" });
    const root = makeFolder({ name: "根", path: "/lib", children: [series, coll] });

    const items = buildCardItems(root, {});

    expect(items).toEqual([
      { type: "series", data: series, id: "sc-/lib/S" },
      { type: "collection", data: coll, id: "mc-/lib/C" },
    ]);
  });

  it("tv 子目录有季目录时按季号排序", () => {
    const s10 = makeFolder({ name: "第十季", path: "/lib/剧/S10" });
    const s2 = makeFolder({ name: "第二季", path: "/lib/剧/S2" });
    const tvNode = makeFolder({
      name: "剧", path: "/lib/剧", folder_type: "tv", children: [s10, s2],
    });
    const root = makeFolder({ name: "根", path: "/lib", children: [tvNode] });

    const tv = buildCardItems(root, {})[0] as Extract<ReturnType<typeof buildCardItems>[0], { type: "tv" }>;

    expect(tv.seasons.map(s => s.name)).toEqual(["第二季", "第十季"]);
    expect(tv.parentNode).toBe(tvNode);
  });

  it("tv 子目录无季目录时季列表退化为该节点自身", () => {
    const tvNode = makeFolder({ name: "扁平", path: "/lib/扁平", folder_type: "tv" });
    const root = makeFolder({ name: "根", path: "/lib", children: [tvNode] });

    const tv = buildCardItems(root, {})[0] as Extract<ReturnType<typeof buildCardItems>[0], { type: "tv" }>;

    expect(tv.seasons).toEqual([tvNode]);
  });
});

describe("buildCardItems — 无 folder_type 时按名称前缀回退分组", () => {
  it("同前缀多个季目录合并成一张 tv 卡片，id 用前缀", () => {
    const a = makeFolder({ name: "老剧 S02", path: "/lib/老剧 S02" });
    const b = makeFolder({ name: "老剧 S01", path: "/lib/老剧 S01" });
    const root = makeFolder({ name: "根", path: "/lib", children: [a, b] });

    const items = buildCardItems(root, {});

    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ type: "tv", seriesName: "老剧", id: "ms-老剧" });
    const tv = items[0] as Extract<typeof items[0], { type: "tv" }>;
    expect(tv.seasons.map(s => s.name)).toEqual(["老剧 S01", "老剧 S02"]);
    // 前缀分组来的 tv 没有 parentNode
    expect(tv.parentNode).toBeUndefined();
  });

  it("同前缀只有一个时不合并，退回普通文件夹卡片", () => {
    const only = makeFolder({ name: "孤剧 S01", path: "/lib/孤剧 S01" });
    const root = makeFolder({ name: "根", path: "/lib", children: [only] });

    expect(buildCardItems(root, {})).toEqual([
      { type: "folder", data: only, id: "f-/lib/孤剧 S01" },
    ]);
  });
});

describe("buildCardItems — 排序与视频追加", () => {
  it("虚拟媒体库子目录置顶到最前，且不按 folder_type 展开", () => {
    const normal = makeFolder({ name: "普通", path: "/lib/普通" });
    const virt = makeFolder({
      name: "库", path: "/lib/库", is_virtual_library: true, folder_type: "tv",
      children: [makeFolder({ name: "第一季", path: "/lib/库/S1" })],
    });
    const root = makeFolder({ name: "根", path: "/lib", children: [normal, virt] });

    const items = buildCardItems(root, {});

    expect(items).toEqual([
      { type: "folder", data: virt, id: "f-/lib/库" },
      { type: "folder", data: normal, id: "f-/lib/普通" },
    ]);
  });

  it("groupedVideos 里的视频追加在末尾，同组内带序号后缀", () => {
    const folder = makeFolder({ name: "子", path: "/lib/子" });
    const root = makeFolder({ name: "根", path: "/lib", children: [folder] });
    const v1 = makeVideo({ file_path: "/lib/1.mkv" });
    const v2 = makeVideo({ file_path: "/lib/2.mkv" });

    const items = buildCardItems(root, { grp: [v1, v2] });

    expect(items).toEqual([
      { type: "folder", data: folder, id: "f-/lib/子" },
      { type: "video", data: v1, id: "v-/lib/1.mkv-0" },
      { type: "video", data: v2, id: "v-/lib/2.mkv-1" },
    ]);
  });
});
