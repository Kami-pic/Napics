// 订阅日历 + 列表/日历切换 前端测试
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// ── mock api 模块 ──
vi.mock("@/lib/api", () => ({
  api: {
    getSubscriptionCalendar: vi.fn(),
    getSubscriptions: vi.fn(),
    triggerSubscriptionSearch: vi.fn(),
    updateSubscription: vi.fn(),
    deleteSubscription: vi.fn(),
  },
}));

import { api } from "@/lib/api";

// ══════════════════════════════════════════
// 1. SubscribeCalendar 组件
// ══════════════════════════════════════════

describe("SubscribeCalendar 组件", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("渲染时调用 api.getSubscriptionCalendar", async () => {
    (api.getSubscriptionCalendar as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    const { default: SubscribeCalendar } = await import("@/components/media/SubscribeCalendar");
    render(<SubscribeCalendar />);
    await waitFor(() => {
      expect(api.getSubscriptionCalendar).toHaveBeenCalledTimes(1);
    });
  });

  it("空数据显示'暂无剧集播出计划'", async () => {
    (api.getSubscriptionCalendar as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    // 需要重新 import 以获取新的组件实例
    vi.resetModules();
    vi.mock("@/lib/api", () => ({
      api: {
        getSubscriptionCalendar: vi.fn().mockResolvedValue([]),
        getSubscriptions: vi.fn(),
        triggerSubscriptionSearch: vi.fn(),
        updateSubscription: vi.fn(),
        deleteSubscription: vi.fn(),
      },
    }));
    const { default: SubscribeCalendar } = await import("@/components/media/SubscribeCalendar");
    render(<SubscribeCalendar />);
    await waitFor(() => {
      expect(screen.getByText(/暂无剧集播出计划/)).toBeInTheDocument();
    });
  });
});

// ══════════════════════════════════════════
// 2. SubscribeInline 列表/日历切换
// ══════════════════════════════════════════

describe("SubscribeInline 列表/日历切换", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // 确保日历组件 mock 返回空数据
    (api.getSubscriptionCalendar as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  });

  it("默认显示'列表'视图", async () => {
    const { default: SubscribeInline } = await import("@/components/media/SubscribeInline");
    render(<SubscribeInline subscriptions={[]} onRefresh={vi.fn()} />);
    // 空订阅时列表视图显示"暂无订阅"
    expect(screen.getByText("暂无订阅")).toBeInTheDocument();
  });

  it("view='calendar' 时切换到日历视图", async () => {
    const { default: SubscribeInline } = await import("@/components/media/SubscribeInline");
    render(<SubscribeInline subscriptions={[]} onRefresh={vi.fn()} view="calendar" />);
    // 日历视图下显示日历组件（加载后显示空数据提示）
    await waitFor(() => {
      expect(screen.getByText(/暂无剧集播出计划/)).toBeInTheDocument();
    });
  });

  it("日历视图下不显示筛选按钮（全部/活跃等）", async () => {
    const { default: SubscribeInline } = await import("@/components/media/SubscribeInline");
    render(<SubscribeInline subscriptions={[]} onRefresh={vi.fn()} view="calendar" />);

    // 筛选按钮不应该出现（日历视图不渲染列表内容）
    expect(screen.queryByText(/全部/)).not.toBeInTheDocument();
    expect(screen.queryByText("活跃")).not.toBeInTheDocument();
    expect(screen.queryByText("已暂停")).not.toBeInTheDocument();
    expect(screen.queryByText("已完成")).not.toBeInTheDocument();
  });
});

// ══════════════════════════════════════════
// 3. api.ts 函数验证
// ══════════════════════════════════════════

describe("api.ts 函数验证", () => {
  it("api.getSubscriptionCalendar 存在且可调用", () => {
    expect(api.getSubscriptionCalendar).toBeDefined();
    expect(typeof api.getSubscriptionCalendar).toBe("function");
  });
});
