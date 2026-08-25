// 锁定移动端 URL 的构造 → 解析往返。
//
// 媒体路径是 Windows / UNC 绝对路径，里面有反斜杠、空格、中文，
// 还可能出现 # & ? 这些在 URL 里有特殊含义的字符。
// 任何一处手拼字符串都会在某个组合上丢内容或截断。
import { describe, it, expect } from "vitest";

import {
  MOBILE_ROUTES,
  MOBILE_NAV_ITEMS,
  libraryUrl,
  libraryDetailUrl,
  playUrl,
  parsePathParam,
  searchUrl,
  parseSearchQuery,
  activeNavKey,
  shouldShowBottomNav,
  discoverUrl,
  parseDiscoverTab,
  discoverDetailUrl,
  parseDiscoverDetailQuery,
} from "@/lib/mobile/mobileRouteUtils";

/** 从生成的 URL 里取出 query 部分，模拟浏览器/Next 的解析 */
function queryOf(url: string): URLSearchParams {
  const [, qs = ""] = url.split("?");
  return new URLSearchParams(qs);
}

const TRICKY_PATHS = [
  String.raw`\\DS218play\share\视频\电影\教父 The Godfather (1972)\教父.mkv`,
  String.raw`C:\Users\shenq\Videos\A Movie & Friends #1 (2020).mp4`,
  String.raw`\\NAS\share\视频\综艺\奇怪的律师禹英禑 S01\第01集 - 什么是律师？.mkv`,
  "/volume1/media/电影/情书 Love Letter (1995)/情书.mkv",
  String.raw`\\NAS\a+b\100%纯爱\file[1].mkv`,
];

describe("媒体路径在 URL 里往返", () => {
  it.each(TRICKY_PATHS)("库列表页往返一致: %s", path => {
    expect(parsePathParam(queryOf(libraryUrl(path)))).toBe(path);
  });

  it.each(TRICKY_PATHS)("详情页往返一致: %s", path => {
    expect(parsePathParam(queryOf(libraryDetailUrl(path)))).toBe(path);
  });

  it.each(TRICKY_PATHS)("播放页往返一致: %s", path => {
    expect(parsePathParam(queryOf(playUrl(path)))).toBe(path);
  });

  it("路径为空时不带 query，库根就是干净的 /m/library", () => {
    expect(libraryUrl()).toBe(MOBILE_ROUTES.library);
    expect(libraryUrl("")).toBe(MOBILE_ROUTES.library);
  });

  it("Server Component 形状的 searchParams 也能解析", () => {
    const path = TRICKY_PATHS[0];
    expect(parsePathParam({ path })).toBe(path);
    // Next 对重复 key 会给数组，取第一个
    expect(parsePathParam({ path: [path, "/other"] })).toBe(path);
    expect(parsePathParam({})).toBe("");
  });
});

describe("搜索 URL", () => {
  it("完整媒体上下文往返一致", () => {
    const query = {
      q: "奇怪的律师禹英禑 S01",
      tab: "pan" as const,
      cnName: "奇怪的律师禹英禑",
      enName: "Extraordinary Attorney Woo",
      originalName: "이상한 변호사 우영우",
      mediaType: "tv",
      folderType: "season",
      season: 1,
      resolution: "1080p",
      savePath: String.raw`\\NAS\share\视频\电视剧`,
    };
    expect(parseSearchQuery(queryOf(searchUrl(query)))).toEqual(query);
  });

  it("默认 tab=bt 不写进 URL，但解析回来仍是 bt", () => {
    const url = searchUrl({ q: "教父", tab: "bt" });
    expect(url).not.toContain("tab=");
    expect(parseSearchQuery(queryOf(url)).tab).toBe("bt");
  });

  it("非法 tab 值退化为 bt，不是 undefined", () => {
    expect(parseSearchQuery({ tab: "垃圾值", q: "x" }).tab).toBe("bt");
  });

  it("季号为 0 或非数字时视为不带季", () => {
    expect(parseSearchQuery({ season: "0" }).season).toBeUndefined();
    expect(parseSearchQuery({ season: "abc" }).season).toBeUndefined();
    expect(parseSearchQuery({ season: "" }).season).toBeUndefined();
    expect(parseSearchQuery({ season: "2" }).season).toBe(2);
  });

  it("空搜索词构造出的 URL 不含空 q", () => {
    expect(searchUrl({ q: "", tab: "bt" })).toBe(MOBILE_ROUTES.search);
  });
});

describe("发现 URL", () => {
  it("榜单 tab 往返一致，缺省时不带 query", () => {
    expect(parseDiscoverTab(queryOf(discoverUrl("douban_tv_hot")))).toBe("douban_tv_hot");
    expect(discoverUrl()).toBe(MOBILE_ROUTES.discover);
    expect(discoverUrl("")).toBe(MOBILE_ROUTES.discover);
    expect(parseDiscoverTab({})).toBe("");
  });

  it("详情上下文完整往返（含中文、韩文、含空格的本地路径）", () => {
    const query = {
      title: "奇怪的律师禹英禑 第一季",
      year: "2022",
      mediaType: "tv",
      source: "douban",
      id: "35651341",
      subtitle: "Extraordinary Attorney Woo / 이상한 변호사 우영우",
      cnName: "奇怪的律师禹英禑",
      enName: "Extraordinary Attorney Woo",
      originalName: "이상한 변호사 우영우",
      localStatus: "owned_low",
      localFolder: String.raw`\\NAS\share\视频\电视剧\奇怪的律师禹英禑 (2022)`,
      tab: "douban_tv_hot",
    };
    expect(parseDiscoverDetailQuery(queryOf(discoverDetailUrl(query)))).toEqual(query);
  });

  it("local_status 为 none 时不占 URL，解析回来是 undefined", () => {
    const url = discoverDetailUrl({ title: "教父", localStatus: "none", localFolder: "" });
    expect(url).not.toContain("ls=");
    const parsed = parseDiscoverDetailQuery(queryOf(url));
    expect(parsed.localStatus).toBeUndefined();
    expect(parsed.localFolder).toBeUndefined();
    expect(parsed.title).toBe("教父");
  });

  it("只有标题时其余字段不写进 URL", () => {
    expect(discoverDetailUrl({ title: "教父" })).toBe(`${MOBILE_ROUTES.discoverDetail}?title=%E6%95%99%E7%88%B6`);
  });
});

describe("底部导航状态", () => {
  it("四个主 Tab 各自的路由能被识别", () => {
    for (const item of MOBILE_NAV_ITEMS) {
      expect(activeNavKey(item.route)).toBe(item.key);
    }
  });

  it("下钻页归属它所属的 Tab", () => {
    expect(activeNavKey("/m/library/detail")).toBe("library");
    expect(activeNavKey("/m/search")).toBe("search");
  });

  it("播放页不属于任何 Tab，也不显示底栏", () => {
    expect(activeNavKey(MOBILE_ROUTES.play)).toBeNull();
    expect(shouldShowBottomNav(MOBILE_ROUTES.play)).toBe(false);
  });

  it("其余移动端页面都显示底栏", () => {
    for (const item of MOBILE_NAV_ITEMS) {
      expect(shouldShowBottomNav(item.route)).toBe(true);
    }
    expect(shouldShowBottomNav("/m/library/detail")).toBe(true);
  });

  it("发现首页认精确路径，不能把 /m/library 也算成发现", () => {
    expect(activeNavKey(MOBILE_ROUTES.discover)).toBe("discover");
    expect(activeNavKey(MOBILE_ROUTES.library)).toBe("library");
  });

  it("发现详情归发现 Tab，且显示底栏", () => {
    expect(activeNavKey(MOBILE_ROUTES.discoverDetail)).toBe("discover");
    expect(shouldShowBottomNav(MOBILE_ROUTES.discoverDetail)).toBe(true);
  });
});
