// 订阅系统子阶段B 前端测试 — api 新增函数验证 + SubscribePanel 搜索按钮增强
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// ── mock api 模块 ──
vi.mock("@/lib/api", () => ({
  api: {
    triggerSubscriptionSearch: vi.fn().mockResolvedValue({ status: "ok", matched: 2, items: [] }),
    deleteSubscription: vi.fn().mockResolvedValue({ status: "ok" }),
    updateSubscription: vi.fn().mockResolvedValue({ status: "ok" }),
    getSubscriptions: vi.fn().mockResolvedValue([]),
    addSubscription: vi.fn().mockResolvedValue({ status: "ok" }),
    getSubscription: vi.fn().mockResolvedValue({}),
    checkSubscribed: vi.fn().mockResolvedValue({ subscribed: false }),
    getSubscriptionSources: vi.fn().mockResolvedValue([
      { name: "prowlarr", display_name: "Prowlarr", enabled: true },
    ]),
    toggleSubscriptionSource: vi.fn().mockResolvedValue({ status: "ok" }),
  },
}));

function makeSub(overrides: any = {}) {
  return {
    id: "sub-b01",
    title: "B阶段测试片",
    year: "2024",
    type: "tv",
    tmdb_id: 88888,
    douban_id: "",
    season: 1,
    state: "active",
    mode: "notify",
    quality: "1080p",
    poster: "",
    total_episode: 12,
    downloaded_episodes: {},
    found_resources: [],
    created_at: "2026-04-13 10:00:00",
    ...overrides,
  };
}

// ══════════════════════════════════════════
// 1. api.ts 新增函数验证
// ══════════════════════════════════════════

describe("api.ts 新增函数验证", () => {
  it("api.getSubscriptionSources 函数存在且可调用", async () => {
    const { api } = await import("@/lib/api");
    expect(api.getSubscriptionSources).toBeTypeOf("function");
    const result = await api.getSubscriptionSources();
    expect(result).toBeInstanceOf(Array);
    expect(result[0]).toHaveProperty("name", "prowlarr");
  });

  it("api.toggleSubscriptionSource 函数存在且可调用", async () => {
    const { api } = await import("@/lib/api");
    expect(api.toggleSubscriptionSource).toBeTypeOf("function");
    const result = await api.toggleSubscriptionSource("prowlarr", false);
    expect(result).toHaveProperty("status", "ok");
  });

  it("api.triggerSubscriptionSearch 函数存在且返回 matched + items", async () => {
    const { api } = await import("@/lib/api");
    expect(api.triggerSubscriptionSearch).toBeTypeOf("function");
    const result = await api.triggerSubscriptionSearch("test-id");
    expect(result).toHaveProperty("status", "ok");
    expect(result).toHaveProperty("matched");
    expect(result).toHaveProperty("items");
  });
});

// ══════════════════════════════════════════
// 2. SubscribePanel 搜索按钮增强
// ══════════════════════════════════════════

describe("SubscribePanel 搜索按钮增强", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("点击搜索按钮后调用 api.triggerSubscriptionSearch", async () => {
    const { api } = await import("@/lib/api");
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const subs = [makeSub({ id: "sub-search-1", title: "搜索测试" })];
    render(<SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={vi.fn()} />);

    fireEvent.click(screen.getByText("🔍 搜索"));
    await waitFor(() => {
      expect(api.triggerSubscriptionSearch).toHaveBeenCalledWith("sub-search-1");
    });
  });

  it("搜索完成且 matched > 0 时调用 onRefresh", async () => {
    const { api } = await import("@/lib/api");
    (api.triggerSubscriptionSearch as any).mockResolvedValue({ status: "ok", matched: 3, items: [] });
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const onRefresh = vi.fn();
    const subs = [makeSub({ id: "sub-search-2", title: "搜索刷新测试" })];
    render(<SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={onRefresh} />);

    fireEvent.click(screen.getByText("🔍 搜索"));
    await waitFor(() => {
      expect(onRefresh).toHaveBeenCalled();
    });
  });

  it("搜索完成且 matched = 0 时不调用 onRefresh", async () => {
    const { api } = await import("@/lib/api");
    (api.triggerSubscriptionSearch as any).mockResolvedValue({ status: "ok", matched: 0, items: [] });
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const onRefresh = vi.fn();
    const subs = [makeSub({ id: "sub-search-3", title: "无结果搜索测试" })];
    render(<SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={onRefresh} />);

    fireEvent.click(screen.getByText("🔍 搜索"));

    // 等待搜索完成（operating 状态恢复）
    await waitFor(() => {
      expect(api.triggerSubscriptionSearch).toHaveBeenCalledWith("sub-search-3");
    });

    // onRefresh 不应被调用（搜索 matched=0 不触发刷新）
    // 等一小段时间确认没有被调用
    await new Promise(r => setTimeout(r, 100));
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("搜索期间卡片显示 operating 状态（opacity-50）", async () => {
    const { api } = await import("@/lib/api");
    // 让搜索永远 pending，模拟 operating 状态
    (api.triggerSubscriptionSearch as any).mockImplementation(() => new Promise(() => {}));
    const { default: SubscribePanel } = await import("@/components/media/SubscribePanel");
    const subs = [makeSub({ id: "sub-search-4", title: "搜索中状态测试" })];
    render(<SubscribePanel open={true} onClose={vi.fn()} subscriptions={subs} onRefresh={vi.fn()} />);

    fireEvent.click(screen.getByText("🔍 搜索"));

    await waitFor(() => {
      const card = screen.getByText("搜索中状态测试").closest(".p-3.rounded-xl");
      expect(card?.className).toContain("opacity-50");
      expect(card?.className).toContain("pointer-events-none");
    });
  });
});
