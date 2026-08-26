// 媒体库分级浏览的页面级行为：渲染了什么、点了往哪跳、异常态是不是白屏。
//
// 能力边界：mock 掉 useRouter 后能断言"调了 push 还是 replace、参数是什么",
// **不能**断言真实浏览器历史栈深度。Android 系统返回键只能真机验证。
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import MobileLibraryClient from "@/components/mobile/MobileLibraryClient";
import MobileLibraryTreeProvider, { useMobileLibraryTree } from "@/components/mobile/MobileLibraryTreeProvider";
import { libraryUrl, libraryDetailUrl, playUrl } from "@/lib/mobile/mobileRouteUtils";
import {
  LIBRARY_TREE,
  MOVIE_NODE,
  COLLECTION_NODE,
  TV_MULTI_SEASON_NODE,
  TV_SINGLE_SEASON_NODE,
  TV_FLAT_NODE,
  TV_EMPTY_SEASON_NODE,
  TV_WITH_EXTRAS_NODE,
  TV_SINGLE_SEASON_WITH_SP_NODE,
  TV_LIBRARY_NODE,
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
    // 卡片封面用它取本地 poster
    getLocalPoster: vi.fn((p: string, cover?: boolean) =>
      `/backend/scrape/poster?path=${encodeURIComponent(p)}${cover ? "&cover=true" : ""}`),
  },
}));
vi.mock("@/lib/api", () => ({ api: mockApi }));

beforeEach(() => {
  mockRouter.push.mockReset();
  mockRouter.replace.mockReset();
  mockApi.getLibraryTree.mockReset();
  mockApi.getLibraryTree.mockResolvedValue(LIBRARY_TREE);
});

/** 代替快速同步：只做它成功后做的那一件事 —— 调 Provider.reload */
function SyncProbe() {
  const { reload } = useMobileLibraryTree();
  return <button type="button" data-testid="sync-reload" onClick={() => void reload()}>同步</button>;
}

async function mount(path: string) {
  render(
    <MobileLibraryTreeProvider>
      <MobileLibraryClient path={path} />
    </MobileLibraryTreeProvider>,
  );
  // 页面自己调 ensureLoaded，等首次加载落地
  await waitFor(() => expect(mockApi.getLibraryTree).toHaveBeenCalled());
  await act(async () => { await Promise.resolve(); });
}

describe("加载态与异常态", () => {
  it("首屏是加载态，不是空白", async () => {
    let resolveTree: (v: unknown) => void = () => {};
    mockApi.getLibraryTree.mockReturnValue(new Promise(r => { resolveTree = r; }));
    render(
      <MobileLibraryTreeProvider>
        <MobileLibraryClient path="" />
      </MobileLibraryTreeProvider>,
    );
    expect(screen.getByText("正在读取媒体库…")).toBeTruthy();
    await act(async () => { resolveTree(LIBRARY_TREE); });
  });

  it("树加载失败 → 明确文案 + 重试按钮，重试会再发请求", async () => {
    mockApi.getLibraryTree.mockRejectedValueOnce(new Error("boom"));
    await mount("");
    expect(screen.getByText(/媒体库加载失败/)).toBeTruthy();

    mockApi.getLibraryTree.mockResolvedValue(LIBRARY_TREE);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "重试" })); });
    await waitFor(() => expect(mockApi.getLibraryTree).toHaveBeenCalledTimes(2));
    expect(screen.getByText("电影")).toBeTruthy();
  });

  it("path 不在树里 → 提示可能已被移动，而不是空目录", async () => {
    await mount("D:\\影视\\已经删掉的目录");
    expect(screen.getByText(/不在媒体库里/)).toBeTruthy();
  });

  it("季目录全空 → 空态文案，并给出下一步（搜索 / 同步）", async () => {
    await mount(TV_EMPTY_SEASON_NODE.path);
    expect(screen.getByText("这个目录里还没有已入库的视频")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "搜索资源" }));
    expect(mockRouter.push.mock.calls.at(-1)![0]).toContain("/m/resource");

    fireEvent.click(screen.getByRole("button", { name: "去同步" }));
    expect(mockRouter.push).toHaveBeenLastCalledWith("/m/downloads");
  });
});

describe("分级浏览与跳转", () => {
  it("库根显示一级分类，点进去是下钻 push", async () => {
    await mount("");
    fireEvent.click(screen.getByText("电影"));
    expect(mockRouter.push).toHaveBeenCalledWith(libraryUrl("D:\\影视\\电影"));
    expect(mockRouter.replace).not.toHaveBeenCalled();
  });

  it("虚拟库进入后按剧目呈现（显示原始目录名）", async () => {
    await mount(TV_LIBRARY_NODE.path);
    expect(screen.getByText("三体 (2023)")).toBeTruthy();
    expect(screen.getByText("沙丘：预言 (2024)")).toBeTruthy();
  });

  it("单电影卡片直接进详情，不再下钻一层", async () => {
    await mount("D:\\影视\\电影");
    // 这是目录卡片，显示的是原始目录名（不带扩展名）
    fireEvent.click(screen.getByText(MOVIE_NODE.name));
    expect(mockRouter.push).toHaveBeenCalledWith(
      libraryDetailUrl(MOVIE_NODE.videos[0].file_path),
    );
  });

  it("TV 多季显示季列表，季徽标带季号", async () => {
    await mount(TV_MULTI_SEASON_NODE.path);
    expect(screen.getByLabelText("季列表")).toBeTruthy();
    // 季卡片徽标是「季号 · 集数」
    expect(screen.getByText(/^S01 · \d+ 集$/)).toBeTruthy();
    expect(screen.getByText(/^S02 · \d+ 集$/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Season 1" }));
    expect(mockRouter.push).toHaveBeenCalledWith(libraryUrl(TV_MULTI_SEASON_NODE.children[1].path));
  });

  it("TV 单季直接是集列表，页头同时有剧名和季名", async () => {
    await mount(TV_SINGLE_SEASON_NODE.path);
    expect(screen.getByRole("heading", { name: "沙丘：预言 (2024)" })).toBeTruthy();
    expect(screen.getByText("Season 1")).toBeTruthy();
    expect(screen.getByLabelText("视频列表")).toBeTruthy();
    expect(screen.queryByLabelText("季列表")).toBeNull();
  });

  it("扁平 TV 直接列直属集，顺序是 E1/E2/E10", async () => {
    await mount(TV_FLAT_NODE.path);
    // 卡片按钮的 aria-label 就是原始文件名（详情入口，不含"播放"前缀）
    const cards = within(screen.getByLabelText("视频列表"))
      .getAllByRole("button")
      .filter(b => !(b.getAttribute("aria-label") || "").startsWith("播放"));
    expect(cards.map(c => c.getAttribute("aria-label"))).toEqual([
      "Friends E1.mkv", "Friends E2.mkv", "Friends E10.mkv",
    ]);
  });

  it("多季剧的剧场版单独一段，不和正片混在一起", async () => {
    await mount(TV_WITH_EXTRAS_NODE.path);
    expect(screen.getByLabelText("季列表")).toBeTruthy();

    const extras = screen.getByLabelText("其他视频（剧场版 / 特别篇）");
    const cards = within(extras).getAllByRole("button")
      .filter(b => !(b.getAttribute("aria-label") || "").startsWith("播放"));
    expect(cards.length).toBe(1);
    expect(cards[0].getAttribute("aria-label")).toBe("剧场版 咆哮.mkv");
  });

  it("单季剧的 SP 也走独立分段", async () => {
    await mount(TV_SINGLE_SEASON_WITH_SP_NODE.path);
    const countCards = (label: string) =>
      within(screen.getByLabelText(label)).getAllByRole("button")
        .filter(b => !(b.getAttribute("aria-label") || "").startsWith("播放")).length;
    expect(countCards("视频列表")).toBe(2);
    expect(countCards("其他视频（剧场版 / 特别篇）")).toBe(1);
  });

  it("collection 的子目录和直属视频同屏，两者都能点", async () => {
    await mount(COLLECTION_NODE.path);
    expect(screen.getByLabelText("目录列表")).toBeTruthy();
    expect(screen.getByLabelText("视频列表")).toBeTruthy();

    fireEvent.click(screen.getByText("美国队长 (2011)"));
    expect(mockRouter.push).toHaveBeenLastCalledWith(
      libraryDetailUrl(COLLECTION_NODE.children[0].videos[0].file_path),
    );

    fireEvent.click(screen.getByText("雷神 Thor (2011).mkv"));
    expect(mockRouter.push).toHaveBeenLastCalledWith(
      libraryDetailUrl(COLLECTION_NODE.videos[0].file_path),
    );
  });

  it("集条目进详情，行尾播放按钮才去播放页", async () => {
    await mount(TV_FLAT_NODE.path);
    const first = TV_FLAT_NODE.videos[2];   // 排序后的第一条是 E1

    fireEvent.click(screen.getByText(first.file_name));
    expect(mockRouter.push).toHaveBeenLastCalledWith(libraryDetailUrl(first.file_path));

    fireEvent.click(screen.getByRole("button", { name: `播放 ${first.file_name}` }));
    expect(mockRouter.push).toHaveBeenLastCalledWith(playUrl(first.file_path));
  });
});

describe("返回键", () => {
  it("库根不渲染返回键", async () => {
    await mount("");
    expect(screen.queryByLabelText("返回")).toBeNull();
  });

  it("下钻页返回键指向父目录，而不是只调 back()", async () => {
    await mount(TV_MULTI_SEASON_NODE.children[1].path);
    fireEvent.click(screen.getByLabelText("返回"));
    expect(mockRouter.push).toHaveBeenCalledWith(libraryUrl(TV_MULTI_SEASON_NODE.path));
    expect(mockRouter.back).not.toHaveBeenCalled();
  });

  it("一级分类的返回键回到库根（父 path 是空串，不等于没有父）", async () => {
    await mount(TV_LIBRARY_NODE.path);
    fireEvent.click(screen.getByLabelText("返回"));
    expect(mockRouter.push).toHaveBeenCalledWith(libraryUrl(""));
  });
});

describe("同步后缓存失效", () => {
  it("树 reload 后媒体库页能看到新入库的视频", async () => {
    // 第一次返回的扁平剧只有一集
    const oneEpisode = {
      ...LIBRARY_TREE,
      children: LIBRARY_TREE.children.map(top =>
        top === TV_LIBRARY_NODE
          ? {
            ...TV_LIBRARY_NODE,
            children: [{ ...TV_FLAT_NODE, videos: [TV_FLAT_NODE.videos[2]] }],
          }
          : top,
      ),
    };
    mockApi.getLibraryTree.mockResolvedValueOnce(oneEpisode);

    render(
      <MobileLibraryTreeProvider>
        <MobileLibraryClient path={TV_FLAT_NODE.path} />
        <SyncProbe />
      </MobileLibraryTreeProvider>,
    );
    const cardCount = () =>
      within(screen.getByLabelText("视频列表")).getAllByRole("button")
        .filter(b => !(b.getAttribute("aria-label") || "").startsWith("播放")).length;
    await waitFor(() => expect(cardCount()).toBe(1));

    // 快速同步成功后走的就是 Provider.reload（见 useMobileQuickSync 的 done 分支）
    mockApi.getLibraryTree.mockResolvedValue(LIBRARY_TREE);
    await act(async () => { fireEvent.click(screen.getByTestId("sync-reload")); });
    await waitFor(() => expect(cardCount()).toBe(3));
  });
});

describe("整树只拉一次", () => {
  it("同一 Provider 下换 path 重渲染不重复请求", async () => {
    const { rerender } = render(
      <MobileLibraryTreeProvider>
        <MobileLibraryClient path="" />
      </MobileLibraryTreeProvider>,
    );
    await waitFor(() => expect(mockApi.getLibraryTree).toHaveBeenCalledTimes(1));
    rerender(
      <MobileLibraryTreeProvider>
        <MobileLibraryClient path={TV_FLAT_NODE.path} />
      </MobileLibraryTreeProvider>,
    );
    await act(async () => { await Promise.resolve(); });
    expect(mockApi.getLibraryTree).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("视频列表")).toBeTruthy();
  });
});
