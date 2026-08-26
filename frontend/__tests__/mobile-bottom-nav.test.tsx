// 底栏行为：主 Tab 用 replace（返回键不在 Tab 间循环），
// 以及**已经在某个 Tab 的下钻页时，再点这个 Tab 要回到该 Tab 的根**。
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import MobileBottomNav from "@/components/mobile/MobileBottomNav";
import { MOBILE_ROUTES } from "@/lib/mobile/mobileRouteUtils";

const { mockRouter, mockPath } = vi.hoisted(() => ({
  mockRouter: { push: vi.fn(), replace: vi.fn(), back: vi.fn() },
  mockPath: { value: "/m/library" },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => mockPath.value,
}));

const { mockPlugins } = vi.hoisted(() => ({
  mockPlugins: { value: { hasDiscover: true, ready: true } as Record<string, unknown> },
}));
vi.mock("@/components/mobile/MobileProviders", () => ({
  useMobilePlugins: () => mockPlugins.value,
}));

beforeEach(() => {
  mockRouter.push.mockReset();
  mockRouter.replace.mockReset();
  mockPath.value = "/m/library";
  mockPlugins.value = { hasDiscover: true, ready: true };
});

describe("底部导航", () => {
  it("在媒体库的下钻页点「媒体库」→ 回库根（丢掉 path 参数）", () => {
    mockPath.value = "/m/library";
    render(<MobileBottomNav />);
    fireEvent.click(screen.getByRole("button", { name: "媒体库" }));
    // 目标不带 ?path=，所以从任何下钻层级点它都回到根
    expect(mockRouter.replace).toHaveBeenCalledWith(MOBILE_ROUTES.library);
  });

  it("在详情页点「媒体库」同样回库根", () => {
    mockPath.value = "/m/library/detail";
    render(<MobileBottomNav />);
    fireEvent.click(screen.getByRole("button", { name: "媒体库" }));
    expect(mockRouter.replace).toHaveBeenCalledWith(MOBILE_ROUTES.library);
  });

  it("主 Tab 一律用 replace，不用 push", () => {
    render(<MobileBottomNav />);
    for (const label of ["媒体库", "发现", "搜索", "下载"]) {
      fireEvent.click(screen.getByRole("button", { name: label }));
    }
    expect(mockRouter.push).not.toHaveBeenCalled();
    expect(mockRouter.replace).toHaveBeenCalledTimes(4);
  });

  it("当前 Tab 高亮，其余不高亮", () => {
    mockPath.value = "/m/library/detail";
    render(<MobileBottomNav />);
    expect(screen.getByRole("button", { name: "媒体库" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("button", { name: "发现" }).getAttribute("aria-current")).toBeNull();
  });

  it("已经在当前 Tab 的首屏时，再点它回到顶部（否则点了没有任何反馈）", () => {
    const scrollTo = vi.fn();
    vi.stubGlobal("scrollTo", scrollTo);
    mockPath.value = "/m/library";
    render(<MobileBottomNav />);

    fireEvent.click(screen.getByRole("button", { name: "媒体库" }));
    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "smooth" });

    // 点别的 Tab 不滚动（那是页面切换，本来就从顶部开始）
    scrollTo.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "发现" }));
    expect(scrollTo).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("资源搜索页也高亮「搜索」（它没有自己的 Tab）", () => {
    mockPath.value = "/m/resource";
    render(<MobileBottomNav />);
    expect(screen.getByRole("button", { name: "搜索" }).getAttribute("aria-current")).toBe("page");
  });
});

describe("按插件可用性裁剪 Tab", () => {
  it("没装 feature-discover 时「发现」和「搜索」都不出现", () => {
    // 两个都依赖它：发现是榜单，搜索是豆瓣片名搜索。
    // 留着只能进去看一句"不可用"，白占两格
    mockPlugins.value = { hasDiscover: false, ready: true };
    render(<MobileBottomNav />);

    expect(screen.queryByRole("button", { name: "发现" })).toBeNull();
    expect(screen.queryByRole("button", { name: "搜索" })).toBeNull();
    expect(screen.getByRole("button", { name: "媒体库" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "下载" })).toBeTruthy();
  });

  it("插件状态还没查完时先按「有」渲染，避免闪现", () => {
    mockPlugins.value = { hasDiscover: false, ready: false };
    render(<MobileBottomNav />);
    expect(screen.getByRole("button", { name: "发现" })).toBeTruthy();
  });
});
