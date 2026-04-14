// 订阅系统深度测试 — 覆盖交互操作、边界情况、hook 逻辑、props 传递
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { renderHook, act } from "@testing-library/react";
import type { DoubanHotItem } from "@/types";

// ── mock api 模块（SubscribePanel 交互测试需要） ──
vi.mock("@/lib/api", () => ({
  api: {
    triggerSubscriptionSearch: vi.fn().mockResolvedValue({ status: "ok" }),
    deleteSubscription: vi.fn().mockResolvedValue({ status: "ok" }),
    updateSubscription: vi.fn().mockResolvedValue({ status: "ok" }),
    getSubscriptions: vi.fn().mockResolvedValue([]),
    addSubscription: vi.fn().mockResolvedValue({ status: "ok" }),
    getSubscription: vi.fn().mockResolvedValue({}),
    checkSubscribed: vi.fn().mockResolvedValue({ subscribed: false }),
  },
}));

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

function makeSub(overrides: any = {}) {
  return {
    id: "sub-001",
    title: "测试电影",
    year: "2026",
    type: "movie",
    tmdb_id: 99999,
    douban_id: "",
    season: undefined,
    state: "active",
    mode: "notify",
    quality: "1080p",
    poster: "",
    total_episode: 0,
    downloaded_episodes: {},
    found_resources: [],
    created_at: "2026-04-13 10:00:00",
    ...overrides,
  };
}


// ══════════════════════════════════════════
// 1. SubscribePanel 交互深度测试
// ══════════════════════════════════════════

describe("SubscribePanel 交互深度测试", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("点击'🔍 搜索'按钮触发 api.triggerSubscriptionSearch", async () => {
    const { api } = await import("@/lib/api");
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const subs = [makeSub({ id: "sub-100", title: "搜索测试片" })];
    render(<SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={vi.fn()} />);

    fireEvent.click(screen.getByText("🔍 搜索"));
    await waitFor(() => {
      expect(api.triggerSubscriptionSearch).toHaveBeenCalledWith("sub-100");
    });
  });

  it("点击'🗑 删除'按钮触发 api.deleteSubscription 并调用 onRefresh", async () => {
    const { api } = await import("@/lib/api");
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const onRefresh = vi.fn();
    const subs = [makeSub({ id: "sub-200", title: "删除测试片" })];
    render(<SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={onRefresh} />);

    fireEvent.click(screen.getByText("🗑 删除"));
    await waitFor(() => {
      expect(api.deleteSubscription).toHaveBeenCalledWith("sub-200");
    });
    await waitFor(() => {
      expect(onRefresh).toHaveBeenCalled();
    });
  });

  it("点击'⏸ 暂停'按钮触发 api.updateSubscription 并调用 onRefresh", async () => {
    const { api } = await import("@/lib/api");
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const onRefresh = vi.fn();
    const subs = [makeSub({ id: "sub-300", title: "暂停测试片", state: "active" })];
    render(<SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={onRefresh} />);

    fireEvent.click(screen.getByText("⏸ 暂停"));
    await waitFor(() => {
      expect(api.updateSubscription).toHaveBeenCalledWith("sub-300", { state: "paused" });
    });
    await waitFor(() => {
      expect(onRefresh).toHaveBeenCalled();
    });
  });

  it("operating 状态卡片显示半透明+禁止点击（opacity-50 pointer-events-none）", async () => {
    const { api } = await import("@/lib/api");
    // 让 deleteSubscription 永远 pending，模拟 operating 状态
    (api.deleteSubscription as any).mockImplementation(() => new Promise(() => {}));
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const subs = [makeSub({ id: "sub-400", title: "操作中测试片" })];
    render(<SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={vi.fn()} />);

    // 点击删除触发 operating 状态
    fireEvent.click(screen.getByText("🗑 删除"));

    // 卡片容器应该有 opacity-50 和 pointer-events-none
    await waitFor(() => {
      const card = screen.getByText("操作中测试片").closest(".p-3.rounded-xl");
      expect(card?.className).toContain("opacity-50");
      expect(card?.className).toContain("pointer-events-none");
    });
  });

  it("多个订阅时筛选切换正确过滤（全部→活跃→已完成）", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const subs = [
      makeSub({ id: "1", title: "活跃片A", state: "active" }),
      makeSub({ id: "2", title: "暂停片B", state: "paused" }),
      makeSub({ id: "3", title: "完成片C", state: "completed" }),
    ];
    render(<SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={vi.fn()} />);

    // 默认"全部"：三个都在
    expect(screen.getByText("活跃片A")).toBeInTheDocument();
    expect(screen.getByText("暂停片B")).toBeInTheDocument();
    expect(screen.getByText("完成片C")).toBeInTheDocument();

    // 切到"活跃"
    const activeButtons = screen.getAllByText("活跃");
    fireEvent.click(activeButtons[0]); // 筛选按钮
    expect(screen.getByText("活跃片A")).toBeInTheDocument();
    expect(screen.queryByText("暂停片B")).not.toBeInTheDocument();
    expect(screen.queryByText("完成片C")).not.toBeInTheDocument();

    // 切到"已完成"
    fireEvent.click(screen.getByText("已完成"));
    expect(screen.queryByText("活跃片A")).not.toBeInTheDocument();
    expect(screen.queryByText("暂停片B")).not.toBeInTheDocument();
    expect(screen.getByText("完成片C")).toBeInTheDocument();
  });

  it("点击面板外部背景触发 onClose", async () => {
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const onClose = vi.fn();
    render(<SubscribePanel open={true} onClose={onClose} subscriptions={[]} onRefresh={vi.fn()} />);

    // 面板最外层是 fixed inset-0 的 div，点击它（而非内部面板）触发 onClose
    const overlay = document.querySelector(".fixed.inset-0.z-50");
    expect(overlay).not.toBeNull();
    // 直接点击 overlay 自身（e.target === e.currentTarget）
    fireEvent.click(overlay!);
    expect(onClose).toHaveBeenCalledOnce();
  });
});


// ══════════════════════════════════════════
// 2. DiscoverCard 边界情况
// ══════════════════════════════════════════

describe("DiscoverCard 边界情况", () => {
  it("local_status='owned_low' 时不显示📌（本地角标优先）", async () => {
    const { default: DiscoverCard } = await import("@/components/media/DiscoverCard");
    render(
      <DiscoverCard
        item={makeItem({ local_status: "owned_low" })}
        index={0} isActive={false} showRank={false}
        onClick={vi.fn()} isSubscribed={true}
      />
    );
    // 本地角标"升级·订阅"应该显示（合并标签）
    expect(screen.getByText(/升级·订阅/)).toBeInTheDocument();
    // 📌不应该单独显示
    expect(screen.queryByText("📌 已订阅")).not.toBeInTheDocument();
  });

  it("showRank=true 且 isSubscribed=true 时，📌角标在底部信息行", async () => {
    const { default: DiscoverCard } = await import("@/components/media/DiscoverCard");
    const { container } = render(
      <DiscoverCard
        item={makeItem({ local_status: undefined })}
        index={0} isActive={false} showRank={true}
        onClick={vi.fn()} isSubscribed={true}
      />
    );
    const badge = screen.getByText("📌 已订阅");
    expect(badge).toBeInTheDocument();
    // 状态标签在底部信息行，不是绝对定位角标
    expect(badge.className).toContain("text-violet-400");
  });

  it("showRank=false 且 isSubscribed=true 时，📌角标在底部信息行", async () => {
    const { default: DiscoverCard } = await import("@/components/media/DiscoverCard");
    render(
      <DiscoverCard
        item={makeItem({ local_status: undefined })}
        index={0} isActive={false} showRank={false}
        onClick={vi.fn()} isSubscribed={true}
      />
    );
    const badge = screen.getByText("📌 已订阅");
    expect(badge.className).toContain("text-violet-400");
  });

  it("isActive=true 时卡片边框高亮（border-blue-500）", async () => {
    const { default: DiscoverCard } = await import("@/components/media/DiscoverCard");
    const { container } = render(
      <DiscoverCard
        item={makeItem()} index={0}
        isActive={true} showRank={false}
        onClick={vi.fn()}
      />
    );
    const card = container.querySelector("[data-discover-card]");
    expect(card?.className).toContain("border-blue-500");
  });

  it("isActive=false 时卡片无高亮边框", async () => {
    const { default: DiscoverCard } = await import("@/components/media/DiscoverCard");
    const { container } = render(
      <DiscoverCard
        item={makeItem()} index={0}
        isActive={false} showRank={false}
        onClick={vi.fn()}
      />
    );
    const card = container.querySelector("[data-discover-card]");
    expect(card?.className).not.toContain("border-blue-500");
  });
});


// ══════════════════════════════════════════
// 3. ExpandDetail 边界情况
// ══════════════════════════════════════════

describe("ExpandDetail 边界情况", () => {
  it("loading=true 时不显示订阅按钮（显示加载动画）", async () => {
    const { default: ExpandDetail } = await import("@/components/media/ExpandDetail");
    render(
      <ExpandDetail
        item={makeItem()}
        detail={{ found: true, title: "流浪地球3", year: "2027", overview: "测试", source: "tmdb" } as any}
        loading={true}
        onSearch={vi.fn()} onClose={vi.fn()} onRetry={vi.fn()}
        onSubscribe={vi.fn()} isSubscribed={false}
      />
    );
    // loading 时显示加载动画文本
    expect(screen.getByText("加载详情...")).toBeInTheDocument();
    // 不应该显示订阅按钮
    expect(screen.queryByText("📌 订阅")).not.toBeInTheDocument();
    expect(screen.queryByText("📌 已订阅")).not.toBeInTheDocument();
  });

  it("detail=null 且 loading=false 时（NoDetailFallback）订阅按钮仍然可用", async () => {
    const { default: ExpandDetail } = await import("@/components/media/ExpandDetail");
    const onSubscribe = vi.fn();
    render(
      <ExpandDetail
        item={makeItem()}
        detail={null}
        loading={false}
        onSearch={vi.fn()} onClose={vi.fn()} onRetry={vi.fn()}
        onSubscribe={onSubscribe} isSubscribed={false}
      />
    );
    const btn = screen.getByText("📌 订阅");
    expect(btn).toBeInTheDocument();
    expect(btn).not.toBeDisabled();
    fireEvent.click(btn);
    expect(onSubscribe).toHaveBeenCalledOnce();
  });

  it("已订阅状态下点击按钮不触发 onSubscribe（disabled 属性）", async () => {
    const { default: ExpandDetail } = await import("@/components/media/ExpandDetail");
    const onSubscribe = vi.fn();
    render(
      <ExpandDetail
        item={makeItem()}
        detail={{ found: true, title: "流浪地球3", year: "2027", overview: "测试", source: "tmdb" } as any}
        loading={false}
        onSearch={vi.fn()} onClose={vi.fn()} onRetry={vi.fn()}
        onSubscribe={onSubscribe} isSubscribed={true}
      />
    );
    const btn = screen.getByText("📌 已订阅");
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(onSubscribe).not.toHaveBeenCalled();
  });
});


// ══════════════════════════════════════════
// 4. Header 边界情况
// ══════════════════════════════════════════

describe("Header 边界情况", () => {
  const defaultProps = {
    stats: { total: 100, lowRes: 10, missingSub: 5 },
    onOpenSettings: vi.fn(),
    scanning: false,
    onStartScan: vi.fn(),
    onStopScan: vi.fn(),
    onOpenDownloads: vi.fn(),
  };

  it("scanning=true 时显示'停止'按钮而非'扫描媒体库'", async () => {
    const { default: Header } = await import("@/components/layout/Header");
    render(<Header {...defaultProps} scanning={true} />);
    expect(screen.getByText("停止")).toBeInTheDocument();
    expect(screen.queryByText("扫描媒体库")).not.toBeInTheDocument();
  });

  it("scanning=false 时显示'扫描媒体库'按钮而非'停止'", async () => {
    const { default: Header } = await import("@/components/layout/Header");
    render(<Header {...defaultProps} scanning={false} />);
    expect(screen.getByText("扫描媒体库")).toBeInTheDocument();
    expect(screen.queryByText("停止")).not.toBeInTheDocument();
  });

  it("subscriptionCount 为 undefined 时不显示角标", async () => {
    const { default: Header } = await import("@/components/layout/Header");
    const { container } = render(
      <Header {...defaultProps} onOpenSubscriptions={vi.fn()} />
    );
    // subscriptionCount 默认值为 0，不显示角标
    const badge = container.querySelector(".bg-violet-600");
    expect(badge).toBeNull();
  });

  it("scanning=true 时点击'停止'按钮触发 onStopScan", async () => {
    const { default: Header } = await import("@/components/layout/Header");
    const onStopScan = vi.fn();
    render(<Header {...defaultProps} scanning={true} onStopScan={onStopScan} />);
    fireEvent.click(screen.getByText("停止"));
    expect(onStopScan).toHaveBeenCalledOnce();
  });
});


// ══════════════════════════════════════════
// 5. useSubscriptions hook 逻辑测试
// ══════════════════════════════════════════

describe("useSubscriptions hook — isSubscribed 逻辑", () => {
  it("tmdb_id 匹配返回 true", async () => {
    const { api } = await import("@/lib/api");
    (api.getSubscriptions as any).mockResolvedValue([
      makeSub({ id: "s1", tmdb_id: 12345, state: "active", season: undefined }),
    ]);

    const { useSubscriptions } = await import("@/hooks/useSubscriptions");
    const { result } = renderHook(() => useSubscriptions());

    // 等待初始加载完成
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.isSubscribed(12345)).toBe(true);
  });

  it("title+year 匹配返回 true", async () => {
    const { api } = await import("@/lib/api");
    (api.getSubscriptions as any).mockResolvedValue([
      makeSub({ id: "s2", title: "三体", year: "2025", tmdb_id: undefined, state: "active", season: undefined }),
    ]);

    const { useSubscriptions } = await import("@/hooks/useSubscriptions");
    const { result } = renderHook(() => useSubscriptions());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.isSubscribed(undefined, "三体", "2025")).toBe(true);
  });

  it("completed 状态的订阅不算已订阅", async () => {
    const { api } = await import("@/lib/api");
    (api.getSubscriptions as any).mockResolvedValue([
      makeSub({ id: "s3", tmdb_id: 67890, state: "completed", season: undefined }),
    ]);

    const { useSubscriptions } = await import("@/hooks/useSubscriptions");
    const { result } = renderHook(() => useSubscriptions());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.isSubscribed(67890)).toBe(false);
  });

  it("不匹配返回 false", async () => {
    const { api } = await import("@/lib/api");
    (api.getSubscriptions as any).mockResolvedValue([
      makeSub({ id: "s4", tmdb_id: 11111, title: "某片", year: "2024", state: "active", season: undefined }),
    ]);

    const { useSubscriptions } = await import("@/hooks/useSubscriptions");
    const { result } = renderHook(() => useSubscriptions());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // tmdb_id 不匹配
    expect(result.current.isSubscribed(99999)).toBe(false);
    // title+year 不匹配
    expect(result.current.isSubscribed(undefined, "不存在的片", "2024")).toBe(false);
  });
});


// ══════════════════════════════════════════
// 6. RecommendTabContent props 传递验证
// ══════════════════════════════════════════

describe("RecommendTabContent props 传递验证", () => {
  it("RecommendTabContentProps 接口包含 onSubscribe 和 checkSubscribed 字段", async () => {
    // 通过 TypeScript 编译验证：如果接口不包含这两个字段，下面的代码会编译失败
    const { default: RecommendTabContent } = await import("@/components/media/RecommendTabContent");
    type Props = React.ComponentProps<typeof RecommendTabContent>;

    // 类型级别验证：确保 onSubscribe 和 checkSubscribed 是 Props 的可选字段
    const testProps: Pick<Props, "onSubscribe" | "checkSubscribed"> = {
      onSubscribe: (item: any, detail: any) => {},
      checkSubscribed: (item: any) => false,
    };
    expect(testProps.onSubscribe).toBeTypeOf("function");
    expect(testProps.checkSubscribed).toBeTypeOf("function");
  });

  it("组件能接收 onSubscribe 和 checkSubscribed props 而不报错", async () => {
    const { default: RecommendTabContent } = await import("@/components/media/RecommendTabContent");
    const mockGridRef = { current: null };

    // 渲染组件，传入 onSubscribe 和 checkSubscribed，不应抛错
    expect(() => {
      render(
        <RecommendTabContent
          tabKey="douban_movie"
          isActive={false}
          isSearchMode={false}
          data={{ items: [], loading: false, error: false, hasMore: false, page: 0 }}
          colCount={5}
          expandedIndex={null}
          detail={null}
          detailLoading={false}
          loadingMore={false}
          rowEndIndex={-1}
          gridRef={mockGridRef}
          onCardClick={vi.fn()}
          onSelectMedia={vi.fn()}
          onCloseExpand={vi.fn()}
          onRetry={vi.fn()}
          onRefreshWithSource={vi.fn()}
          onLoadMore={vi.fn()}
          onRetryTab={vi.fn()}
          onSubscribe={vi.fn()}
          checkSubscribed={vi.fn()}
        />
      );
    }).not.toThrow();
  });
});
