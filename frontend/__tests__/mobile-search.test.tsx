// 锁定移动端搜索页：URL 是唯一触发源、BT 与网盘两套独立交互、
// 提交下载走 qb 且不选通道、网盘复制必须带提取码。
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import MobileSearchClient from "@/components/mobile/MobileSearchClient";
import MobileProviders from "@/components/mobile/MobileProviders";
import { mockEventSourceInstances, resetMockEventSource } from "./helpers/mockEventSource";
import type { MobileSearchQuery } from "@/lib/mobile/mobileRouteUtils";

const { mockRouter } = vi.hoisted(() => ({
  mockRouter: { replace: vi.fn(), push: vi.fn(), back: vi.fn() },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/m/search",
}));

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    getConfig: vi.fn(),
    getLibraryTree: vi.fn(),
    getProviders: vi.fn(),
    getSearchSources: vi.fn(),
    getAIStatus: vi.fn(),
    searchStream: vi.fn(),
    searchSingle: vi.fn(),
    searchPan: vi.fn(),
    searchSource: vi.fn(),
    aiSearchRecommend: vi.fn(),
    submitDownload: vi.fn(),
    checkPath: vi.fn(),
    listDirectories: vi.fn(),
  },
}));
vi.mock("@/lib/api", () => ({ api: mockApi }));
vi.mock("@/lib/api/plugins", () => ({ fetchPlugins: vi.fn().mockResolvedValue([]) }));

const SAVE_PATH = String.raw`\\NAS\share\视频\电视剧`;

function makeQuery(over: Partial<MobileSearchQuery> = {}): MobileSearchQuery {
  return { q: "奇怪的律师禹英禑", tab: "bt", ...over };
}

function renderSearch(query: MobileSearchQuery) {
  return render(
    <MobileProviders>
      <MobileSearchClient query={query} />
    </MobileProviders>,
  );
}

/** 让挂载时的 SSE 主搜索吐一批结果出来 */
async function emitBtResults(results: unknown[]) {
  const es = mockEventSourceInstances.at(-1);
  if (!es) throw new Error("EventSource 没有被创建，BT 搜索没发起");
  await act(async () => {
    es.emitMessage({ type: "source_done", source: "prowlarr", status: "done", count: results.length, results });
    es.emitMessage({ type: "done" });
  });
}

function btResult(over: Record<string, unknown> = {}) {
  return {
    title: "Extraordinary.Attorney.Woo.S01E01.1080p.WEB-DL.mkv",
    size_gb: 2.5,
    indexer: "SomeTracker",
    seeders: 12,
    leechers: 1,
    download_url: "magnet:?xt=urn:btih:abc",
    quality_tag: "1080p WEB-DL",
    quality: {
      resolution: "1080p", source: "WEB-DL", video_codec: "x264", audio_codec: "AAC",
      has_chinese_sub: true, release_group: "", is_surround: false, display: "1080p WEB-DL",
    },
    quality_rank: 3,
    ...over,
  };
}

function panResult(over: Record<string, unknown> = {}) {
  return {
    title: "奇怪的律师禹英禑 全16集",
    clean_title: "奇怪的律师禹英禑",
    pan_type: "quark",
    share_url: "https://pan.quark.cn/s/abcdef",
    password: "8x2k",
    source: "pansearch",
    mounted: false,
    resolution: "1080p",
    size_gb: 30,
    is_complete: true,
    file_count: 16,
    alive: true,
    ...over,
  };
}

beforeEach(() => {
  resetMockEventSource();
  Object.values(mockApi).forEach(fn => fn.mockReset());
  mockRouter.replace.mockReset();
  mockApi.getConfig.mockResolvedValue({ scan_paths: [SAVE_PATH] });
  mockApi.getLibraryTree.mockResolvedValue({
    name: "媒体库", path: "", videos: [], video_count: 0, has_cover: false, children: [],
  });
  mockApi.getProviders.mockResolvedValue({ search: [], panSearch: [] });
  mockApi.getSearchSources.mockResolvedValue({ sources: [] });
  mockApi.getAIStatus.mockResolvedValue({ enabled: false, features: {} });
  mockApi.searchStream.mockReturnValue("/backend/api/search/stream?query=x");
  mockApi.searchSingle.mockResolvedValue({ bt_results: [] });
  mockApi.searchPan.mockResolvedValue({ results: [], groups: {}, source_statuses: [], total: 0 });
  mockApi.submitDownload.mockResolvedValue({ success: true });
  mockApi.checkPath.mockResolvedValue({ path: SAVE_PATH, exists: true, is_dir: true, readable: true, hint: "" });
  mockApi.listDirectories.mockResolvedValue({
    path: SAVE_PATH, parent: "", separator: "\\", is_root_list: false, dirs: [], error: "",
  });
});

describe("搜索触发方式", () => {
  it("URL 里有词就自动发起 BT 搜索", async () => {
    renderSearch(makeQuery());
    await waitFor(() => expect(mockEventSourceInstances.length).toBeGreaterThan(0));
    expect(mockApi.searchStream).toHaveBeenCalled();
  });

  it("提交新词只改 URL，不直接搜（否则会双搜）", async () => {
    renderSearch(makeQuery({ q: "" }));
    // 空词时不该发起搜索
    expect(mockEventSourceInstances.length).toBe(0);

    fireEvent.change(screen.getByLabelText("搜索词"), { target: { value: "教父" } });
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    expect(mockRouter.replace).toHaveBeenCalledWith(expect.stringContaining("q=%E6%95%99%E7%88%B6"));
    // URL 还没真正变（测试里 router 是 mock），所以不该有新的搜索发起
    expect(mockEventSourceInstances.length).toBe(0);
  });

  it("空搜索词不提交", async () => {
    renderSearch(makeQuery({ q: "" }));
    expect(screen.getByRole("button", { name: "搜索" })).toBeDisabled();
  });

  it("切换到网盘 Tab 会改 URL 并发起网盘搜索", async () => {
    renderSearch(makeQuery());
    fireEvent.click(screen.getByRole("tab", { name: /网盘/ }));

    expect(mockRouter.replace).toHaveBeenCalledWith(expect.stringContaining("tab=pan"));
  });

  it("URL 带 tab=pan 时直接搜网盘，不搜 BT", async () => {
    mockApi.searchPan.mockResolvedValue({
      results: [panResult()], groups: {}, source_statuses: [], total: 1,
    });
    renderSearch(makeQuery({ tab: "pan" }));

    await waitFor(() => expect(mockApi.searchPan).toHaveBeenCalledWith("奇怪的律师禹英禑", undefined, expect.anything()));
  });
});

describe("BT 结果与提交下载", () => {
  it("结果里显示体积、做种和质量标签", async () => {
    renderSearch(makeQuery());
    await waitFor(() => expect(mockEventSourceInstances.length).toBeGreaterThan(0));
    await emitBtResults([btResult()]);

    await waitFor(() => expect(screen.getByText(/Extraordinary\.Attorney\.Woo/)).toBeInTheDocument());
    expect(screen.getByText("2.50 GB")).toBeInTheDocument();
    expect(screen.getByText("12 做种")).toBeInTheDocument();
    expect(screen.getByText("中字")).toBeInTheDocument();
  });

  it("没有做种信息的直搜结果显示成磁力链接，不显示 0 做种", async () => {
    renderSearch(makeQuery());
    await waitFor(() => expect(mockEventSourceInstances.length).toBeGreaterThan(0));
    await emitBtResults([btResult({ seeders: 0, size_gb: 0 })]);

    await waitFor(() => expect(screen.getByText("磁力链接")).toBeInTheDocument());
    expect(screen.queryByText("0 做种")).not.toBeInTheDocument();
  });

  it("提交下载走 qb 通道，界面上没有通道选择", async () => {
    renderSearch(makeQuery());
    await waitFor(() => expect(mockEventSourceInstances.length).toBeGreaterThan(0));
    await emitBtResults([btResult()]);
    await waitFor(() => expect(screen.getByRole("button", { name: "下载到本地" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "下载到本地" }));

    await waitFor(() => expect(mockApi.submitDownload).toHaveBeenCalled());
    const payload = mockApi.submitDownload.mock.calls[0][0];
    expect(payload.channel).toBe("qb");
    expect(payload.download_url).toBe("magnet:?xt=urn:btih:abc");
    // P0 不暴露 alist，界面上不该有通道相关控件
    expect(screen.queryByText(/网盘离线|通道/)).not.toBeInTheDocument();
  });

  it("没填保存路径时用 Config 的默认扫描路径", async () => {
    renderSearch(makeQuery());
    await waitFor(() => expect(mockEventSourceInstances.length).toBeGreaterThan(0));
    await emitBtResults([btResult()]);
    await waitFor(() => expect(screen.getByRole("button", { name: "下载到本地" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "下载到本地" }));

    await waitFor(() => expect(mockApi.submitDownload).toHaveBeenCalled());
    expect(mockApi.submitDownload.mock.calls[0][0].save_path).toBe(SAVE_PATH);
  });

  it("提交失败时把后端原因显示出来", async () => {
    mockApi.submitDownload.mockResolvedValue({ success: false, error: "qBittorrent 连不上" });

    renderSearch(makeQuery());
    await waitFor(() => expect(mockEventSourceInstances.length).toBeGreaterThan(0));
    await emitBtResults([btResult()]);
    await waitFor(() => expect(screen.getByRole("button", { name: "下载到本地" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "下载到本地" }));

    await waitFor(() => expect(screen.getByText(/qBittorrent 连不上/)).toBeInTheDocument());
  });

  it("提交中禁用所有下载按钮，防止连点提交多次", async () => {
    let release!: (v: unknown) => void;
    mockApi.submitDownload.mockReturnValue(new Promise(res => { release = res; }));

    renderSearch(makeQuery());
    await waitFor(() => expect(mockEventSourceInstances.length).toBeGreaterThan(0));
    await emitBtResults([btResult(), btResult({ title: "另一个版本", download_url: "magnet:?xt=urn:btih:def" })]);
    await waitFor(() => expect(screen.getAllByRole("button", { name: /下载到本地|提交中/ })).toHaveLength(2));

    fireEvent.click(screen.getAllByRole("button", { name: "下载到本地" })[0]);

    await waitFor(() => {
      const buttons = screen.getAllByRole("button", { name: /下载到本地|提交中/ });
      expect(buttons.every(b => (b as HTMLButtonElement).disabled)).toBe(true);
    });
    expect(screen.getByRole("button", { name: "提交中…" })).toBeInTheDocument();

    await act(async () => { release({ success: true }); });
  });

  it("没搜到结果时说清楚是没搜到，不是还在加载", async () => {
    renderSearch(makeQuery());
    await waitFor(() => expect(mockEventSourceInstances.length).toBeGreaterThan(0));
    await emitBtResults([]);

    await waitFor(() => expect(screen.getByText(/没搜到结果/)).toBeInTheDocument());
  });
});

describe("网盘结果", () => {
  async function renderPan() {
    mockApi.searchPan.mockResolvedValue({
      results: [panResult()], groups: {}, source_statuses: [], total: 1,
    });
    renderSearch(makeQuery({ tab: "pan" }));
    await waitFor(() => expect(screen.getByText("奇怪的律师禹英禑")).toBeInTheDocument());
  }

  it("展示网盘类型、提取码等信息", async () => {
    await renderPan();
    expect(screen.getByText("夸克")).toBeInTheDocument();
    expect(screen.getByText("提取码 8x2k")).toBeInTheDocument();
    expect(screen.getByText("16 个文件")).toBeInTheDocument();
  });

  it("复制按钮一次带上链接和提取码", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });

    await renderPan();
    fireEvent.click(screen.getByRole("button", { name: "复制链接和提取码" }));

    await waitFor(() => expect(writeText).toHaveBeenCalled());
    const copied = writeText.mock.calls[0][0];
    expect(copied).toContain("https://pan.quark.cn/s/abcdef");
    // 回归：只复制链接会把提取码丢掉，换个 App 打开就进不去
    expect(copied).toContain("8x2k");
  });

  it("复制失败时明确提示，不静默", async () => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockRejectedValue(new Error("非安全上下文")) },
      configurable: true,
    });
    // 降级路径也失败
    document.execCommand = vi.fn().mockReturnValue(false);

    await renderPan();
    fireEvent.click(screen.getByRole("button", { name: "复制链接和提取码" }));

    await waitFor(() => expect(screen.getByText(/复制失败/)).toBeInTheDocument());
  });

  it("没有提取码时按钮文案随之变化", async () => {
    mockApi.searchPan.mockResolvedValue({
      results: [panResult({ password: "" })], groups: {}, source_statuses: [], total: 1,
    });
    renderSearch(makeQuery({ tab: "pan" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "复制链接" })).toBeInTheDocument());
  });

  it("失效链接有明确标记", async () => {
    mockApi.searchPan.mockResolvedValue({
      results: [panResult({ alive: false })], groups: {}, source_statuses: [], total: 1,
    });
    renderSearch(makeQuery({ tab: "pan" }));
    await waitFor(() => expect(screen.getByText("链接可能已失效")).toBeInTheDocument());
  });

  it("网盘 Tab 不出现任何暗示能转存或跟踪任务的文案", async () => {
    await renderPan();
    expect(screen.getByText(/暂不代为转存/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /转存|离线下载/ })).not.toBeInTheDocument();
  });

  it("网盘 Tab 不显示保存路径（P0 不下载到本地）", async () => {
    await renderPan();
    expect(screen.queryByLabelText("保存目录")).not.toBeInTheDocument();
  });
});
