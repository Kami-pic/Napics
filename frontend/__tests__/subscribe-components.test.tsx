// 订阅系统前端组件测试 — 覆盖 ExpandDetail 订阅按钮、DiscoverCard 角标、SubscribePanel 面板、useSubscriptions hook、api.ts 函数
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import type { DoubanHotItem } from "@/types";

// ── 测试数据工厂 ──

function makeItem(overrides: Partial<DoubanHotItem> = {}): DoubanHotItem {
  return {
    title: "流浪地球3",
    year: "2027",
    rating: 8.5,
    cover_url: "https://example.com/poster.jpg",
    douban_id: "12345",
    media_type: "movie",
    genres: ["科幻", "冒险"],
    countries: ["中国"],
    episode: "",
    episodes_info: "",
    subtitle: "The Wandering Earth 3",
    ...overrides,
  };
}

// ══════════════════════════════════════════
// ExpandDetail — 订阅按钮
// ══════════════════════════════════════════

describe("ExpandDetail 订阅按钮", () => {
  it("未订阅时显示'📌 订阅'按钮", async () => {
    const { default: ExpandDetail } = await import("@/components/media/ExpandDetail");
    const item = makeItem();
    render(
      <ExpandDetail
        item={item}
        detail={{ found: true, title: "流浪地球3", year: "2027", overview: "测试", source: "tmdb" } as any}
        loading={false}
        onSearch={vi.fn()}
        onClose={vi.fn()}
        onRetry={vi.fn()}
        onSubscribe={vi.fn()}
        isSubscribed={false}
      />
    );
    const btn = screen.getByText("📌 订阅");
    expect(btn).toBeInTheDocument();
    expect(btn).not.toBeDisabled();
  });

  it("已订阅时显示'📌 已订阅'且可点击取消订阅", async () => {
    const { default: ExpandDetail } = await import("@/components/media/ExpandDetail");
    const item = makeItem();
    const onUnsubscribe = vi.fn();
    render(
      <ExpandDetail
        item={item}
        detail={{ found: true, title: "流浪地球3", year: "2027", overview: "测试", source: "tmdb" } as any}
        loading={false}
        onSearch={vi.fn()}
        onClose={vi.fn()}
        onRetry={vi.fn()}
        onSubscribe={vi.fn()}
        onUnsubscribe={onUnsubscribe}
        isSubscribed={true}
      />
    );
    const btn = screen.getByText("📌 已订阅");
    expect(btn).toBeInTheDocument();
    expect(btn).not.toBeDisabled();
    expect(btn).toHaveAttribute("title", "点击取消订阅");
  });

  it("点击订阅按钮触发 onSubscribe 回调", async () => {
    const { default: ExpandDetail } = await import("@/components/media/ExpandDetail");
    const onSubscribe = vi.fn();
    render(
      <ExpandDetail
        item={makeItem()}
        detail={{ found: true, title: "流浪地球3", year: "2027", overview: "测试", source: "tmdb" } as any}
        loading={false}
        onSearch={vi.fn()}
        onClose={vi.fn()}
        onRetry={vi.fn()}
        onSubscribe={onSubscribe}
        isSubscribed={false}
      />
    );
    fireEvent.click(screen.getByText("📌 订阅"));
    expect(onSubscribe).toHaveBeenCalledOnce();
  });

  it("不传 onSubscribe 时不显示订阅按钮", async () => {
    const { default: ExpandDetail } = await import("@/components/media/ExpandDetail");
    render(
      <ExpandDetail
        item={makeItem()}
        detail={{ found: true, title: "流浪地球3", year: "2027", overview: "测试", source: "tmdb" } as any}
        loading={false}
        onSearch={vi.fn()}
        onClose={vi.fn()}
        onRetry={vi.fn()}
      />
    );
    expect(screen.queryByText("📌 订阅")).not.toBeInTheDocument();
    expect(screen.queryByText("📌 已订阅")).not.toBeInTheDocument();
  });

  it("无详情 fallback 时也显示订阅按钮", async () => {
    const { default: ExpandDetail } = await import("@/components/media/ExpandDetail");
    render(
      <ExpandDetail
        item={makeItem()}
        detail={null}
        loading={false}
        onSearch={vi.fn()}
        onClose={vi.fn()}
        onRetry={vi.fn()}
        onSubscribe={vi.fn()}
        isSubscribed={false}
      />
    );
    expect(screen.getByText("📌 订阅")).toBeInTheDocument();
  });
});

// ══════════════════════════════════════════
// DiscoverCard — 订阅角标
// ══════════════════════════════════════════

describe("DiscoverCard 订阅角标", () => {
  it("已订阅且无本地资源时显示📌角标", async () => {
    const { default: DiscoverCard } = await import("@/components/media/DiscoverCard");
    const { container } = render(
      <DiscoverCard
        item={makeItem({ local_status: undefined })}
        index={0}
        isActive={false}
        showRank={false}
        onClick={vi.fn()}
        isSubscribed={true}
      />
    );
    expect(screen.getByText("📌 已订阅")).toBeInTheDocument();
  });

  it("已订阅但已有本地资源时不显示📌角标（本地角标优先）", async () => {
    const { default: DiscoverCard } = await import("@/components/media/DiscoverCard");
    render(
      <DiscoverCard
        item={makeItem({ local_status: "owned_high" })}
        index={0}
        isActive={false}
        showRank={false}
        onClick={vi.fn()}
        isSubscribed={true}
      />
    );
    expect(screen.queryByText("📌")).not.toBeInTheDocument();
    expect(screen.getByText(/已有/)).toBeInTheDocument();
  });

  it("未订阅时不显示📌角标", async () => {
    const { default: DiscoverCard } = await import("@/components/media/DiscoverCard");
    render(
      <DiscoverCard
        item={makeItem()}
        index={0}
        isActive={false}
        showRank={false}
        onClick={vi.fn()}
        isSubscribed={false}
      />
    );
    expect(screen.queryByText("📌")).not.toBeInTheDocument();
  });

  it("不传 isSubscribed 时不显示📌角标", async () => {
    const { default: DiscoverCard } = await import("@/components/media/DiscoverCard");
    render(
      <DiscoverCard
        item={makeItem()}
        index={0}
        isActive={false}
        showRank={false}
        onClick={vi.fn()}
      />
    );
    expect(screen.queryByText("📌")).not.toBeInTheDocument();
  });
});


// ══════════════════════════════════════════
// SubscribePanel — 订阅管理面板
// ══════════════════════════════════════════

describe("SubscribePanel 面板", () => {
  const makeSub = (overrides: any = {}) => ({
    id: "sub-001",
    title: "测试电影",
    year: "2026",
    type: "movie",
    tmdb_id: 99999,
    douban_id: "",
    season: null,
    state: "active",
    mode: "notify",
    quality: "1080p",
    poster: "",
    total_episode: 0,
    downloaded_episodes: {},
    found_resources: [],
    created_at: "2026-04-13 10:00:00",
    ...overrides,
  });

  it("open=false 时不渲染", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const { container } = render(
      <SubscribePanel open={false} onClose={vi.fn()} subscriptions={[]} onRefresh={vi.fn()} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("open=true 时渲染面板标题", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    render(
      <SubscribePanel open={true} onClose={vi.fn()} subscriptions={[]} onRefresh={vi.fn()} />
    );
    expect(screen.getByText("我的订阅")).toBeInTheDocument();
  });

  it("空订阅列表显示'暂无订阅'", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    render(
      <SubscribePanel open={true} onClose={vi.fn()} subscriptions={[]} onRefresh={vi.fn()} />
    );
    expect(screen.getByText("暂无订阅")).toBeInTheDocument();
  });

  it("渲染订阅卡片 — 标题+状态+质量", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const subs = [makeSub({ title: "流浪地球3", quality: "2160p", state: "active" })];
    render(
      <SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={vi.fn()} />
    );
    expect(screen.getByText("流浪地球3")).toBeInTheDocument();
    // "活跃"同时出现在筛选按钮和卡片状态标签中，用 getAllByText
    expect(screen.getAllByText("活跃").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("2160p")).toBeInTheDocument();
  });

  it("剧集订阅显示进度条", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const subs = [makeSub({
      title: "三体",
      type: "tv",
      total_episode: 30,
      downloaded_episodes: { "1": {}, "2": {}, "3": {} },
    })];
    render(
      <SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={vi.fn()} />
    );
    expect(screen.getByText("3/30")).toBeInTheDocument();
  });

  it("筛选按钮 — 全部/活跃/已暂停/已完成", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const subs = [
      makeSub({ id: "1", title: "活跃片", state: "active" }),
      makeSub({ id: "2", title: "暂停片", state: "paused" }),
      makeSub({ id: "3", title: "完成片", state: "completed" }),
    ];
    render(
      <SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={vi.fn()} />
    );
    // 默认全部 — 三个卡片都在
    expect(screen.getByText("活跃片")).toBeInTheDocument();
    expect(screen.getByText("暂停片")).toBeInTheDocument();
    expect(screen.getByText("完成片")).toBeInTheDocument();

    // 点击"已暂停"筛选按钮（筛选栏中的按钮，用 getAllByText 取第一个）
    const pausedButtons = screen.getAllByText("已暂停");
    // 第一个是筛选按钮，点击它
    fireEvent.click(pausedButtons[0]);
    expect(screen.getByText("暂停片")).toBeInTheDocument();
    expect(screen.queryByText("活跃片")).not.toBeInTheDocument();
    expect(screen.queryByText("完成片")).not.toBeInTheDocument();
  });

  it("暂停按钮文案 — active 显示'⏸ 暂停'，paused 显示'▶ 恢复'", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const subs = [
      makeSub({ id: "1", title: "活跃片", state: "active" }),
      makeSub({ id: "2", title: "暂停片", state: "paused" }),
    ];
    render(
      <SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={vi.fn()} />
    );
    expect(screen.getByText("⏸ 暂停")).toBeInTheDocument();
    expect(screen.getByText("▶ 恢复")).toBeInTheDocument();
  });

  it("关闭按钮触发 onClose", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const onClose = vi.fn();
    render(
      <SubscribePanel open={true} onClose={onClose} subscriptions={[]} onRefresh={vi.fn()} />
    );
    fireEvent.click(screen.getByText("✕"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("有新资源时显示🔔角标", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const subs = [makeSub({
      title: "有新资源的片",
      found_resources: [{ title: "资源1" }],
    })];
    render(
      <SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={vi.fn()} />
    );
    expect(screen.getByText("🔔")).toBeInTheDocument();
  });

  it("电影显示'电影'标签，剧集显示'剧集'标签", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const subs = [
      makeSub({ id: "1", title: "电影A", type: "movie" }),
      makeSub({ id: "2", title: "剧集B", type: "tv" }),
    ];
    render(
      <SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={vi.fn()} />
    );
    expect(screen.getByText("电影A")).toBeInTheDocument();
    expect(screen.getByText("剧集B")).toBeInTheDocument();
    expect(screen.getAllByText("电影").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("剧集").length).toBeGreaterThanOrEqual(1);
  });
});

// ══════════════════════════════════════════
// api.ts — 订阅 API 函数导出
// ══════════════════════════════════════════

describe("api.ts 订阅函数导出", () => {
  it("所有订阅 API 函数存在", async () => {
    const { api } = await import("@/lib/api");
    expect(api.getSubscriptions).toBeTypeOf("function");
    expect(api.getSubscription).toBeTypeOf("function");
    expect(api.addSubscription).toBeTypeOf("function");
    expect(api.updateSubscription).toBeTypeOf("function");
    expect(api.deleteSubscription).toBeTypeOf("function");
    expect(api.triggerSubscriptionSearch).toBeTypeOf("function");
    expect(api.checkSubscribed).toBeTypeOf("function");
  });
});

// ══════════════════════════════════════════
// useSubscriptions hook — 逻辑测试
// ══════════════════════════════════════════

describe("useSubscriptions hook 导出", () => {
  it("hook 函数可导入", async () => {
    const { useSubscriptions } = await import("@/hooks/useSubscriptions");
    expect(useSubscriptions).toBeTypeOf("function");
  });
});

// ══════════════════════════════════════════
// Header — 订阅入口按钮
// ══════════════════════════════════════════

describe("Header 订阅入口", () => {
  const defaultProps = {
    stats: { total: 100, lowRes: 10, missingSub: 5 },
    onOpenSettings: vi.fn(),
    scanning: false,
    onStartScan: vi.fn(),
    onStopScan: vi.fn(),
    onOpenDownloads: vi.fn(),
  };

  it("传入 onOpenSubscriptions 时显示订阅按钮", async () => {
    const { default: Header } = await import("@/components/layout/Header");
    render(<Header {...defaultProps} onOpenSubscriptions={vi.fn()} />);
    expect(screen.getByText("订阅")).toBeInTheDocument();
  });

  it("不传 onOpenSubscriptions 时不显示订阅按钮", async () => {
    const { default: Header } = await import("@/components/layout/Header");
    render(<Header {...defaultProps} />);
    expect(screen.queryByText("订阅")).not.toBeInTheDocument();
  });

  it("点击订阅按钮触发回调", async () => {
    const { default: Header } = await import("@/components/layout/Header");
    const onOpen = vi.fn();
    render(<Header {...defaultProps} onOpenSubscriptions={onOpen} />);
    fireEvent.click(screen.getByText("订阅"));
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it("subscriptionCount > 0 时显示角标数字", async () => {
    const { default: Header } = await import("@/components/layout/Header");
    render(<Header {...defaultProps} onOpenSubscriptions={vi.fn()} subscriptionCount={3} />);
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("subscriptionCount = 0 时不显示角标", async () => {
    const { default: Header } = await import("@/components/layout/Header");
    const { container } = render(<Header {...defaultProps} onOpenSubscriptions={vi.fn()} subscriptionCount={0} />);
    // 角标用的是 w-4 h-4 bg-violet-600 的 span
    const badge = container.querySelector(".bg-violet-600");
    expect(badge).toBeNull();
  });
});
