// 卡片信息口径。用户明确要求「和 web 一致」，所以这里逐条对着桌面 CardGrid 断言：
// 同一批数据两端读出来的数字和标签必须一样。
import { describe, it, expect } from "vitest";

import { folderCardMeta, seasonCardMeta, videoCardMeta } from "@/lib/mobile/mobileCardMeta";
import {
  MOVIE_NODE,
  COLLECTION_NODE,
  SERIES_NODE,
  TV_MULTI_SEASON_NODE,
  TV_WITH_EXTRAS_NODE,
  TV_FLAT_NODE,
  TV_LIBRARY_NODE,
  PLAIN_LEAF_NODE,
} from "./helpers/libraryTreeFixture";

describe("TV 徽标的集数口径", () => {
  it("只累加季目录，不把剧场版/SP 算进集数（桌面是 seasons.reduce）", () => {
    // 夹具：Season 1 一集 + Season 2 一集 + 剧目录下一个剧场版
    // node.video_count 是递归总数（3），会比桌面多算一集
    const meta = folderCardMeta(TV_WITH_EXTRAS_NODE);
    expect(TV_WITH_EXTRAS_NODE.video_count).toBe(3);
    expect(meta.badge?.text).toBe("2 季 · 2 集");
  });

  it("多季剧显示季数与集数", () => {
    const meta = folderCardMeta(TV_MULTI_SEASON_NODE);
    expect(meta.badge?.text).toMatch(/^2 季 · \d+ 集$/);
  });

  it("扁平剧（没有季目录）只显示集数", () => {
    const meta = folderCardMeta(TV_FLAT_NODE);
    expect(meta.badge?.text).toBe(`${TV_FLAT_NODE.video_count} 集`);
  });
});

describe("视频卡的状态标记（桌面的灰点与 ⚠）", () => {
  it("没有影子名也没有整理状态 → 未整理", () => {
    const meta = videoCardMeta({ ...MOVIE_NODE.videos[0], shadow_name: "", organize_status: "" });
    expect(meta.tags.map(t => t.text)).toContain("未整理");
  });

  it("识别失败要标出来", () => {
    const meta = videoCardMeta({ ...MOVIE_NODE.videos[0], organize_status: "scrape_failed" });
    expect(meta.tags.map(t => t.text)).toContain("识别失败");
  });

  it("已整理的条目不加这两个标记", () => {
    const meta = videoCardMeta({ ...MOVIE_NODE.videos[0], shadow_name: "Iron Man (2008)" });
    const texts = meta.tags.map(t => t.text);
    expect(texts).not.toContain("未整理");
    expect(texts).not.toContain("识别失败");
  });

  it("质量标签与桌面同判据：低画质 + 非 SDR 的 HDR 类型", () => {
    const meta = videoCardMeta({
      ...MOVIE_NODE.videos[0], is_low_res: true, hdr_type: "HDR10", shadow_name: "x",
    });
    expect(meta.tags.map(t => t.text)).toEqual(["低画质", "HDR10"]);
    // SDR 不算标签
    const sdr = videoCardMeta({ ...MOVIE_NODE.videos[0], hdr_type: "SDR", shadow_name: "x" });
    expect(sdr.tags.map(t => t.text)).toEqual([]);
  });
});

describe("目录卡与桌面对齐", () => {
  it("series / collection 用 `N 部`，数量取 children.length || video_count", () => {
    expect(folderCardMeta(SERIES_NODE).badge?.text)
      .toBe(`${SERIES_NODE.children.length} 部`);
    expect(folderCardMeta(COLLECTION_NODE).badge?.text)
      .toBe(`${COLLECTION_NODE.children.length} 部`);
  });

  it("虚拟库徽标是分类标签，副信息是「N 个项目」", () => {
    const meta = folderCardMeta(TV_LIBRARY_NODE);
    expect(meta.badge?.tone).toBe("library");
    expect(meta.subtitle).toBe(`${TV_LIBRARY_NODE.video_count} 个项目`);
    expect(meta.cover).toBe(true);
  });

  it("单电影目录显示「分辨率 · 大小」并带质量标签", () => {
    const meta = folderCardMeta(MOVIE_NODE);
    expect(meta.subtitle).toContain(MOVIE_NODE.videos[0].resolution);
    expect(meta.tags.map(t => t.text)).toContain("HDR10");
  });

  it("普通叶子目录标集数", () => {
    expect(folderCardMeta(PLAIN_LEAF_NODE).badge?.text)
      .toBe(`${PLAIN_LEAF_NODE.video_count} 集`);
  });

  it("分类目录（is_category）不标集数：里面是一堆互不相关的片子", () => {
    const meta = folderCardMeta({ ...PLAIN_LEAF_NODE, is_category: true });
    expect(meta.badge).toBeUndefined();
  });

  it("季卡片徽标是「季号 · 集数」", () => {
    const season = TV_MULTI_SEASON_NODE.children[1];
    expect(seasonCardMeta(season).badge?.text).toBe(`S01 · ${season.video_count} 集`);
  });
});
