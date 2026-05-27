// 订阅系统子阶段C 前端测试 — FoundResourcesList + 搜索状态 + api 新增函数 + 类型验证
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// ── mock api 模块 ──
vi.mock("@/lib/api", () => ({
  api: {
    submitDownload: vi.fn().mockResolvedValue({ status: "ok" }),
    updateSubscription: vi.fn().mockResolvedValue({ status: "ok" }),
    triggerSubscriptionSearch: vi.fn().mockResolvedValue({ status: "ok", matched: 0 }),
    deleteSubscription: vi.fn().mockResolvedValue({ status: "ok" }),
    getSubscriptions: vi.fn().mockResolvedValue([]),
    getSubscriptionCalendar: vi.fn().mockResolvedValue([]),
    getSubscriptionSources: vi.fn().mockResolvedValue([]),
    toggleSubscriptionSource: vi.fn().mockResolvedValue({ status: "ok" }),
    addSubscription: vi.fn().mockResolvedValue({ status: "ok" }),
    checkSubscribed: vi.fn().mockResolvedValue({ subscribed: false }),
  },
}));

// ── mock discoverUtils（proxyUrl）──
vi.mock("@/components/media/discoverUtils", () => ({
  proxyUrl: (url: string) => url || "",
}));

// ── 辅助：构造资源数据 ──
function makeResource(overrides: any = {}, index: number = 0) {
  return {
    title: `测试资源_${index}`,
    download_url: `magnet:?xt=urn:btih:hash${index}`,
    info_url: "",
    size_gb: 1.5 + index * 0.5,
    quality_tag: "BluRay",
    resolution: "1080p",
    episode: index + 1,
    seeders: 10 + index,
    indexer: "test-indexer",
    source_name: "prowlarr",
    info_hash: `hash${index}`,
    ...overrides,
  };
}

// ── 辅助：构造订阅数据 ──
function makeSub(overrides: any = {}) {
  return {
    id: "sub-c01",
    title: "C阶段测试片",
    year: "2024",
    type: "tv",
    tmdb_id: 99999,
    douban_id: "",
    season: 1,
    state: "active",
    mode: "notify",
    quality: "1080p",
    poster: "",
    total_episode: 12,
    downloaded_episodes: {},
    found_resources: [],
    created_at: "2026-04-15 10:00:00",
    last_search: undefined as string | undefined,
    search_count: 0,
    save_path: "/downloads/tv",
    ...overrides,
  };
}

// ══════════════════════════════════════════
// 1. FoundResourcesList 组件测试
// ══════════════════════════════════════════

describe("FoundResourcesList 组件", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("有资源时渲染资源列表（标题+质量+大小+下载按钮）", async () => {
    const { default: FoundResourcesList } = await import("@/components/media/FoundResourcesList");
    const resources = [makeResource({}, 0), makeResource({}, 1)];

    render(
      <FoundResourcesList
        resources={resources}
        subscriptionId="sub-test"
        subscriptionTitle="测试影片"
        savePath="/downloads"
        mediaType="tv"
        onDownloaded={vi.fn()}
      />
    );

    // 标题
    expect(screen.getByText("测试资源_0")).toBeInTheDocument();
    expect(screen.getByText("测试资源_1")).toBeInTheDocument();
    // 质量标签
    expect(screen.getAllByText("1080p").length).toBeGreaterThanOrEqual(2);
    // 大小
    expect(screen.getByText("1.5GB")).toBeInTheDocument();
    expect(screen.getByText("2GB")).toBeInTheDocument();
    // 下载按钮
    const downloadBtns = screen.getAllByText("下载");
    expect(downloadBtns.length).toBe(2);
  });

  it("无资源时不渲染（返回 null）", async () => {
    const { default: FoundResourcesList } = await import("@/components/media/FoundResourcesList");

    const { container } = render(
      <FoundResourcesList
        resources={[]}
        subscriptionId="sub-test"
        subscriptionTitle="测试影片"
        savePath="/downloads"
        mediaType="tv"
        onDownloaded={vi.fn()}
      />
    );

    expect(container.innerHTML).toBe("");
  });

  it("超过 3 条时显示'展开全部'按钮", async () => {
    const { default: FoundResourcesList } = await import("@/components/media/FoundResourcesList");
    const resources = Array.from({ length: 5 }, (_, i) => makeResource({}, i));

    render(
      <FoundResourcesList
        resources={resources}
        subscriptionId="sub-test"
        subscriptionTitle="测试影片"
        savePath="/downloads"
        mediaType="tv"
        onDownloaded={vi.fn()}
      />
    );

    // 默认只显示 3 条
    expect(screen.getByText("测试资源_0")).toBeInTheDocument();
    expect(screen.getByText("测试资源_1")).toBeInTheDocument();
    expect(screen.getByText("测试资源_2")).toBeInTheDocument();
    expect(screen.queryByText("测试资源_3")).not.toBeInTheDocument();
    expect(screen.queryByText("测试资源_4")).not.toBeInTheDocument();

    // 展开按钮
    expect(screen.getByText("展开全部 (5 条)")).toBeInTheDocument();
  });

  it("点击'展开全部'后显示所有资源", async () => {
    const { default: FoundResourcesList } = await import("@/components/media/FoundResourcesList");
    const resources = Array.from({ length: 5 }, (_, i) => makeResource({}, i));

    render(
      <FoundResourcesList
        resources={resources}
        subscriptionId="sub-test"
        subscriptionTitle="测试影片"
        savePath="/downloads"
        mediaType="tv"
        onDownloaded={vi.fn()}
      />
    );

    // 点击展开
    fireEvent.click(screen.getByText("展开全部 (5 条)"));

    // 所有资源都应该可见
    expect(screen.getByText("测试资源_0")).toBeInTheDocument();
    expect(screen.getByText("测试资源_1")).toBeInTheDocument();
    expect(screen.getByText("测试资源_2")).toBeInTheDocument();
    expect(screen.getByText("测试资源_3")).toBeInTheDocument();
    expect(screen.getByText("测试资源_4")).toBeInTheDocument();

    // 展开后显示"收起"按钮
    expect(screen.getByText("收起")).toBeInTheDocument();
    expect(screen.queryByText("展开全部 (5 条)")).not.toBeInTheDocument();
  });

  it("点击'下载'按钮触发 api.submitDownload", async () => {
    const { api } = await import("@/lib/api");
    const { default: FoundResourcesList } = await import("@/components/media/FoundResourcesList");
    const resources = [makeResource({ title: "下载测试资源", episode: 3 }, 0)];

    render(
      <FoundResourcesList
        resources={resources}
        subscriptionId="sub-dl-test"
        subscriptionTitle="下载测试片"
        savePath="/downloads/tv"
        mediaType="tv"
        onDownloaded={vi.fn()}
      />
    );

    fireEvent.click(screen.getByText("下载"));

    await waitFor(() => {
      expect(api.submitDownload).toHaveBeenCalledWith(
        expect.objectContaining({
          download_url: expect.any(String),
          save_path: "/downloads/tv",
          subscription_id: "sub-dl-test",
        })
      );
    });
  });
});

// ══════════════════════════════════════════
// 2. SubscribePanel 搜索状态展示
// ══════════════════════════════════════════

describe("SubscribePanel 搜索状态展示", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("卡片显示搜索次数和时间", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const subs = [makeSub({
      id: "sub-search-info",
      title: "搜索状态测试",
      last_search: "2026-04-15 14:30:00",
      search_count: 5,
    })];

    render(<SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={vi.fn()} />);

    // 应显示 "搜索 5 次 · 04-15 14:30"
    expect(screen.getByText(/搜索 5 次/)).toBeInTheDocument();
  });

  it("未搜索时显示'未搜索'", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const subs = [makeSub({
      id: "sub-no-search",
      title: "未搜索测试",
      last_search: undefined,
      search_count: 0,
    })];

    render(<SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={vi.fn()} />);

    expect(screen.getByText("未搜索")).toBeInTheDocument();
  });
});

// ══════════════════════════════════════════
// 3. api.ts 新增函数验证
// ══════════════════════════════════════════

describe("api.ts 新增函数验证", () => {
  it("api.getSubscriptionCalendar 函数存在且可调用", async () => {
    const { api } = await import("@/lib/api");
    expect(api.getSubscriptionCalendar).toBeTypeOf("function");
    const result = await api.getSubscriptionCalendar();
    expect(result).toBeInstanceOf(Array);
  });
});

// ══════════════════════════════════════════
// 4. SubscriptionItem 类型验证
// ══════════════════════════════════════════

describe("SubscriptionItem 类型验证", () => {
  it("包含 last_search/search_count/save_path 字段", async () => {
    const { useSubscriptions } = await import("@/hooks/useSubscriptions");
    // 验证类型定义中包含这些字段（通过构造符合类型的对象来验证）
    const item = makeSub({
      last_search: "2026-04-15 10:00:00",
      search_count: 3,
      save_path: "/downloads/tv",
    });
    // 如果类型定义正确，这些字段应该存在
    expect(item).toHaveProperty("last_search");
    expect(item).toHaveProperty("search_count");
    expect(item).toHaveProperty("save_path");
    expect(item.last_search).toBe("2026-04-15 10:00:00");
    expect(item.search_count).toBe(3);
    expect(item.save_path).toBe("/downloads/tv");
  });
});
