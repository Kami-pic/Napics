// 媒体库内检索：搜的是**已经入库的东西**，纯前端在整树上过滤。
// 和底栏「搜索」（豆瓣找片子）不是一件事。
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import MobileLibraryClient from "@/components/mobile/MobileLibraryClient";
import MobileLibraryTreeProvider from "@/components/mobile/MobileLibraryTreeProvider";
import { searchLibrary, LIBRARY_SEARCH_LIMIT } from "@/lib/mobile/librarySearch";
import { libraryDetailUrl } from "@/lib/mobile/mobileRouteUtils";
import {
  LIBRARY_TREE,
  MOVIE_NODE,
  TV_MULTI_SEASON_NODE,
  TV_FLAT_NODE,
} from "./helpers/libraryTreeFixture";

const { mockRouter } = vi.hoisted(() => ({
  mockRouter: { push: vi.fn(), replace: vi.fn(), back: vi.fn() },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/m/library",
}));

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    getLibraryTree: vi.fn(),
    getLocalPoster: vi.fn((p: string) => `/backend/scrape/poster?path=${encodeURIComponent(p)}`),
  },
}));
vi.mock("@/lib/api", () => ({ api: mockApi }));

// MobileShell 会渲染底栏，底栏要读插件可用性
vi.mock("@/components/mobile/MobileProviders", () => ({
  useMobilePlugins: () => ({ hasDiscover: true, ready: true }),
}));

beforeEach(() => {
  mockRouter.push.mockReset();
  mockApi.getLibraryTree.mockReset();
  mockApi.getLibraryTree.mockResolvedValue(LIBRARY_TREE);
});

async function mount(path = "") {
  render(
    <MobileLibraryTreeProvider>
      <MobileLibraryClient path={path} />
    </MobileLibraryTreeProvider>,
  );
  await waitFor(() => expect(mockApi.getLibraryTree).toHaveBeenCalled());
  await act(async () => { await Promise.resolve(); });
}

describe("searchLibrary 纯函数", () => {
  it("命中目录后不再往它下面找：搜剧名不该被 30 集冲掉", () => {
    const result = searchLibrary(LIBRARY_TREE, "三体");
    const folders = result.hits.filter(h => h.kind === "folder");
    expect(folders.length).toBeGreaterThan(0);
    // 剧目录本身命中了，它下面的集不应再各占一条
    expect(result.hits.some(h => h.kind === "video" && h.video.file_path.includes("三体"))).toBe(false);
  });

  it("跨层级搜：当前在哪一层都能找到深层的东西", () => {
    // 扁平剧的集在第三层，从根搜也要能找到
    const result = searchLibrary(LIBRARY_TREE, "friends e10");
    expect(result.hits.some(h => h.kind === "video" && h.video.file_name === "Friends E10.mkv")).toBe(true);
  });

  it("忽略大小写，也能用清洗名搜到原始名认不出的目录", () => {
    expect(searchLibrary(LIBRARY_TREE, "IRON MAN").hits.length).toBeGreaterThan(0);
    // 夹具里 clean_name 是「三体」而目录名带年份后缀
    expect(searchLibrary(LIBRARY_TREE, "三体").total).toBeGreaterThan(0);
  });

  it("空词与空树返回空结果，不抛", () => {
    expect(searchLibrary(LIBRARY_TREE, "").hits).toEqual([]);
    expect(searchLibrary(LIBRARY_TREE, "   ").total).toBe(0);
    expect(searchLibrary(null, "x").hits).toEqual([]);
  });

  it("超过上限时截断并报告总数", () => {
    // 造一棵有大量同名视频的树
    const many = {
      ...LIBRARY_TREE,
      children: [{
        ...TV_FLAT_NODE,
        videos: Array.from({ length: LIBRARY_SEARCH_LIMIT + 20 }, (_, i) => ({
          ...TV_FLAT_NODE.videos[0],
          file_path: `D:\\x\\命中 ${i}.mkv`,
          file_name: `命中 ${i}.mkv`,
          clean_name: "",
        })),
        name: "无关目录名",
        clean_name: "",
      }],
    };
    const result = searchLibrary(many as never, "命中");
    expect(result.hits.length).toBe(LIBRARY_SEARCH_LIMIT);
    expect(result.total).toBe(LIBRARY_SEARCH_LIMIT + 20);
    expect(result.truncated).toBe(true);
  });
});

describe("媒体库页的检索框", () => {
  it("输入即出结果，不需要提交", async () => {
    await mount("");
    fireEvent.change(screen.getByLabelText("媒体库检索"), { target: { value: "钢铁侠" } });

    const results = screen.getByLabelText("检索结果");
    expect(within(results).getAllByRole("button").length).toBeGreaterThan(0);
    expect(screen.getByText(/命中 \d+ 条/)).toBeTruthy();
  });

  it("检索态下不同时渲染目录浏览（两套内容叠着看不清在哪）", async () => {
    await mount("");
    expect(screen.getByLabelText("目录列表")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("媒体库检索"), { target: { value: "钢铁侠" } });
    expect(screen.queryByLabelText("目录列表")).toBeNull();
    expect(screen.getByLabelText("检索结果")).toBeTruthy();

    // 清空后回到浏览
    fireEvent.change(screen.getByLabelText("媒体库检索"), { target: { value: "" } });
    expect(screen.getByLabelText("目录列表")).toBeTruthy();
  });

  it("点检索结果里的视频进详情", async () => {
    await mount("");
    fireEvent.change(screen.getByLabelText("媒体库检索"), { target: { value: "Friends E10" } });

    const results = screen.getByLabelText("检索结果");
    const card = within(results).getAllByRole("button")
      .find(b => !(b.getAttribute("aria-label") || "").startsWith("播放"))!;
    fireEvent.click(card);
    expect(mockRouter.push).toHaveBeenCalledWith(
      libraryDetailUrl(TV_FLAT_NODE.videos.find(v => v.file_name === "Friends E10.mkv")!.file_path),
    );
  });

  it("搜不到时说清楚是媒体库里没有，而不是目录空", async () => {
    await mount("");
    fireEvent.change(screen.getByLabelText("媒体库检索"), { target: { value: "根本不存在的片名" } });
    expect(screen.getByText(/媒体库里没有匹配/)).toBeTruthy();
    expect(screen.getByText("没有匹配的条目")).toBeTruthy();
  });

  it("在下钻页也能搜整棵树，不限当前目录", async () => {
    await mount(TV_MULTI_SEASON_NODE.path);
    fireEvent.change(screen.getByLabelText("媒体库检索"), { target: { value: "钢铁侠" } });
    // 钢铁侠不在三体目录下，但仍然能搜到
    expect(within(screen.getByLabelText("检索结果")).getAllByRole("button").length).toBeGreaterThan(0);
    expect(screen.queryByText(/媒体库里没有匹配/)).toBeNull();
  });

  it("树还在加载时不显示检索框（搜什么都是空的）", async () => {
    mockApi.getLibraryTree.mockReturnValue(new Promise(() => {}));
    render(
      <MobileLibraryTreeProvider>
        <MobileLibraryClient path="" />
      </MobileLibraryTreeProvider>,
    );
    await act(async () => { await Promise.resolve(); });
    expect(screen.queryByLabelText("媒体库检索")).toBeNull();
  });
});
