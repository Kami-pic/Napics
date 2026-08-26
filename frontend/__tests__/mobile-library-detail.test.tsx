// 移动端视频详情：只有播放 / 搜索资源 / 基本信息 + 刮削信息，
// 刮削触发、改名、整理、批处理**不许出现**（手机误触代价高，也没有确认交互）。
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import MobileLibraryDetailClient from "@/components/mobile/MobileLibraryDetailClient";
import MobileLibraryTreeProvider from "@/components/mobile/MobileLibraryTreeProvider";
import { playUrl, libraryUrl, MOBILE_QUERY_KEYS } from "@/lib/mobile/mobileRouteUtils";
import { LIBRARY_TREE, MOVIE_NODE, TV_MULTI_SEASON_NODE } from "./helpers/libraryTreeFixture";

const { mockRouter } = vi.hoisted(() => ({
  mockRouter: { push: vi.fn(), replace: vi.fn(), back: vi.fn() },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/m/library/detail",
}));

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    getLibraryTree: vi.fn(),
    readScrape: vi.fn(),
    executeScrape: vi.fn(),
    getLocalPoster: vi.fn((p: string) => `/backend/scrape/poster?path=${encodeURIComponent(p)}`),
    getProxiedImage: vi.fn((u: string) => `/backend/proxy/image?url=${encodeURIComponent(u)}`),
  },
}));
vi.mock("@/lib/api", () => ({ api: mockApi }));

const MOVIE_VIDEO = MOVIE_NODE.videos[0];
const EPISODE = TV_MULTI_SEASON_NODE.children[1].videos[2];   // 三体 S01E01.mkv

const SCRAPE_OK = {
  status: "ok",
  data: {
    tmdb_id: 1726,
    media_type: "movie",
    title: "钢铁侠",
    year: "2008",
    rating: 7.6,
    genres: ["动作", "科幻", "冒险"],
    overview: "斯塔克工业的军火商东尼·斯塔克被绑架后打造了一套动力装甲。",
    poster_url: "https://image.tmdb.org/t/p/w500/ironman.jpg",
  },
};

beforeEach(() => {
  mockRouter.push.mockReset();
  mockApi.getLibraryTree.mockReset();
  mockApi.readScrape.mockReset();
  mockApi.getLibraryTree.mockResolvedValue(LIBRARY_TREE);
  mockApi.readScrape.mockResolvedValue(SCRAPE_OK);
});

async function mount(path: string) {
  render(
    <MobileLibraryTreeProvider>
      <MobileLibraryDetailClient path={path} />
    </MobileLibraryTreeProvider>,
  );
  await waitFor(() => expect(mockApi.getLibraryTree).toHaveBeenCalled());
  await act(async () => { await Promise.resolve(); });
}

describe("异常态", () => {
  it("没有 path → 明确提示，不白屏", async () => {
    await mount("");
    expect(screen.getByText("缺少视频路径，无法打开详情")).toBeTruthy();
    expect(mockApi.readScrape).not.toHaveBeenCalled();
  });

  it("视频不在库里 → 提示可能已被移动", async () => {
    await mount("D:\\影视\\电影\\不存在.mkv");
    expect(screen.getByText(/不在媒体库里/)).toBeTruthy();
  });

  it("树加载失败 → 提示后端问题，而不是说视频不存在", async () => {
    mockApi.getLibraryTree.mockRejectedValueOnce(new Error("boom"));
    await mount(MOVIE_VIDEO.file_path);
    expect(screen.getByText(/媒体库加载失败/)).toBeTruthy();
  });

  it("没有刮削结果时仍显示文件信息，只是提示没有刮削信息", async () => {
    mockApi.readScrape.mockResolvedValue({ status: "ok", data: {} });
    await mount(MOVIE_VIDEO.file_path);
    await waitFor(() => expect(screen.getByText(/没有刮削信息/)).toBeTruthy());
    // 标题与信息表都显示原始文件名，所以会出现多处；只要确认它在页面上
    expect(screen.getAllByText(MOVIE_VIDEO.file_name).length).toBeGreaterThan(0);
  });

  it("刮削读取中显示加载态，不先闪一下「没有刮削信息」", async () => {
    // status 的 idle 既是"还没读"也是"读完没数据"，所以这里必须靠 reading
    let resolveScrape: (v: unknown) => void = () => {};
    mockApi.readScrape.mockReturnValue(new Promise(r => { resolveScrape = r; }));
    await mount(MOVIE_VIDEO.file_path);
    expect(screen.getByText("正在读取刮削信息…")).toBeTruthy();
    expect(screen.queryByText(/没有刮削信息/)).toBeNull();

    await act(async () => { resolveScrape(SCRAPE_OK); });
    expect(screen.queryByText("正在读取刮削信息…")).toBeNull();
  });

  it("刮削请求失败与「没有刮削信息」是两种文案", async () => {
    mockApi.readScrape.mockRejectedValue(new Error("boom"));
    await mount(MOVIE_VIDEO.file_path);
    await waitFor(() => expect(screen.getByText(/刮削信息读取失败/)).toBeTruthy());
    expect(screen.queryByText(/在桌面端整理后这里会显示/)).toBeNull();
  });

  it("视频不在库里时错误态有「回媒体库」出口", async () => {
    await mount("D:\\影视\\电影\\不存在.mkv");
    fireEvent.click(screen.getByRole("button", { name: "回媒体库" }));
    expect(mockRouter.push).toHaveBeenCalledWith(libraryUrl("D:\\影视\\电影"));
  });
});

describe("季集定位", () => {
  it("剧集详情显示 SxxExx，页头和正文标题不重复", async () => {
    mockApi.readScrape.mockResolvedValue({
      status: "ok",
      data: { tmdb_id: 1, title: "三体", media_type: "tv" },
    });
    await mount(EPISODE.file_path);
    // 页头是剧名（刮削标题），h2 是"季集 · 本文件清洗名"，不是同一串字
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("三体"));

    const h2 = screen.getByRole("heading", { level: 2 });
    expect(h2.textContent).toContain("S01E01");
    expect(h2.textContent).not.toBe("三体");
  });

  it("电影没有季集号时不硬造标签", async () => {
    await mount(MOVIE_VIDEO.file_path);
    await waitFor(() => expect(screen.getByText("2008")).toBeTruthy());
    expect(screen.queryByText(/S\d\dE\d\d/)).toBeNull();
  });
});

describe("刮削信息与基本信息", () => {
  it("显示标题、年份、评分、类型、简介", async () => {
    await mount(MOVIE_VIDEO.file_path);
    await waitFor(() => expect(screen.getByText("2008")).toBeTruthy());
    expect(screen.getByText("TMDB 7.6")).toBeTruthy();
    expect(screen.getByText("动作 / 科幻 / 冒险")).toBeTruthy();
    expect(screen.getByText(/动力装甲/)).toBeTruthy();
  });

  it("基本信息只列有值的字段，缺失的不显示占位", async () => {
    await mount(MOVIE_VIDEO.file_path);
    expect(screen.getByText("2160p")).toBeTruthy();
    expect(screen.getByText("HDR10")).toBeTruthy();
    expect(screen.getByText(MOVIE_VIDEO.file_path)).toBeTruthy();
    // 夹具里没有 rmvb 之类的空字段值，"—" 不该出现
    expect(screen.queryByText("—")).toBeNull();
  });

  it("刮削读取按 file_path 发起，和桌面同一个端点", async () => {
    await mount(MOVIE_VIDEO.file_path);
    expect(mockApi.readScrape).toHaveBeenCalledWith(MOVIE_VIDEO.file_path, false);
  });
});

describe("三个允许的操作", () => {
  it("播放按钮进 /m/play，不在详情页里直接起播", async () => {
    await mount(MOVIE_VIDEO.file_path);
    fireEvent.click(screen.getByRole("button", { name: /播放/ }));
    expect(mockRouter.push).toHaveBeenCalledWith(playUrl(MOVIE_VIDEO.file_path));
  });

  it("搜索资源带上结构化上下文（清洗名 / 类型 / 分辨率）", async () => {
    await mount(MOVIE_VIDEO.file_path);
    await waitFor(() => expect(screen.getByText("2008")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /搜索资源/ }));

    const url = new URL(mockRouter.push.mock.calls.at(-1)![0], "http://x");
    expect(url.pathname).toBe("/m/search");
    const q = url.searchParams;
    expect(q.get(MOBILE_QUERY_KEYS.query)).toBe("钢铁侠");
    expect(q.get(MOBILE_QUERY_KEYS.cnName)).toBe("钢铁侠");
    expect(q.get(MOBILE_QUERY_KEYS.enName)).toBe("Iron Man");
    expect(q.get(MOBILE_QUERY_KEYS.mediaType)).toBe("movie");
    expect(q.get(MOBILE_QUERY_KEYS.resolution)).toBe("2160p");
  });

  it("剧集的搜索上下文带季号（从 SxxExx 提取）", async () => {
    mockApi.readScrape.mockResolvedValue({ status: "ok", data: { tmdb_id: 1, title: "三体", media_type: "tv" } });
    await mount(EPISODE.file_path);
    fireEvent.click(screen.getByRole("button", { name: /搜索资源/ }));
    const url = new URL(mockRouter.push.mock.calls.at(-1)![0], "http://x");
    expect(url.searchParams.get(MOBILE_QUERY_KEYS.season)).toBe("1");
  });

  it("返回键回到视频所在目录", async () => {
    await mount(EPISODE.file_path);
    fireEvent.click(screen.getByLabelText("返回"));
    expect(mockRouter.push).toHaveBeenCalledWith(libraryUrl(TV_MULTI_SEASON_NODE.children[1].path));
  });
});

describe("桌面专属操作不渲染", () => {
  it("没有刮削 / 改名 / 整理 / 删除 / 移动 / 批量按钮", async () => {
    await mount(MOVIE_VIDEO.file_path);
    for (const name of [/刮削/, /重新匹配/, /改名/, /重命名/, /整理/, /删除/, /移动/, /批量/]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
    // 内容区里只有播放和搜索资源两个按钮。
    // 不能数全页按钮：页头返回键 + 底栏四个 Tab 也算 button。
    const main = screen.getByRole("main");
    expect(within(main).getAllByRole("button").length).toBe(2);
  });

  it("不会调用 /scrape/execute", async () => {
    await mount(MOVIE_VIDEO.file_path);
    expect(mockApi.executeScrape).not.toHaveBeenCalled();
  });
});

describe("海报回退顺序", () => {
  it("先本地 poster，加载失败才换远程代理", async () => {
    await mount(MOVIE_VIDEO.file_path);
    await waitFor(() => expect(screen.getByText("2008")).toBeTruthy());
    const img = document.querySelector("img")!;
    expect(img.getAttribute("src")).toContain("/scrape/poster");

    fireEvent.error(img);
    expect(document.querySelector("img")!.getAttribute("src")).toContain("/proxy/image");
  });

  it("远程也失败就显示文字占位，不留破图", async () => {
    await mount(MOVIE_VIDEO.file_path);
    await waitFor(() => expect(screen.getByText("2008")).toBeTruthy());
    fireEvent.error(document.querySelector("img")!);
    fireEvent.error(document.querySelector("img")!);
    expect(document.querySelector("img")).toBeNull();
  });
});
