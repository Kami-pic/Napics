// 底栏「搜索」= 按片名找片子（豆瓣搜索），不是资源搜索。
// 资源搜索只能从详情页的「搜索资源」进 /m/resource。
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import MobileDiscoverSearchClient from "@/components/mobile/MobileDiscoverSearchClient";
import {
  MOBILE_QUERY_KEYS,
  MOBILE_ROUTES,
  MOBILE_NAV_ITEMS,
  activeNavKey,
  discoverSearchUrl,
} from "@/lib/mobile/mobileRouteUtils";

const { mockRouter } = vi.hoisted(() => ({
  mockRouter: { push: vi.fn(), replace: vi.fn(), back: vi.fn() },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/m/search",
}));

const { mockPlugins } = vi.hoisted(() => ({
  mockPlugins: { value: { hasDiscover: true, ready: true } as Record<string, unknown> },
}));
vi.mock("@/components/mobile/MobileProviders", () => ({
  useMobilePlugins: () => mockPlugins.value,
}));

const { mockApi } = vi.hoisted(() => ({
  mockApi: { doubanSearch: vi.fn() },
}));
vi.mock("@/lib/api", () => ({ api: mockApi }));

const CANDIDATES = {
  candidates: [
    {
      douban_id: "3820180", title: "沙丘", year: "2021", rating: 7.8,
      poster_url: "https://img9.doubanio.com/view/photo/x.jpg",
      media_type: "movie", local_status: "owned_high", local_folder: "D:\\影视\\沙丘 (2021)",
    },
    {
      douban_id: "35651341", title: "沙丘：预言", year: "2024", rating: 6.5,
      poster_url: "https://img9.doubanio.com/view/photo/y.jpg",
      media_type: "tv", local_status: "none",
    },
  ],
};

beforeEach(() => {
  mockRouter.push.mockReset();
  mockRouter.replace.mockReset();
  mockApi.doubanSearch.mockReset();
  mockApi.doubanSearch.mockResolvedValue(CANDIDATES);
  mockPlugins.value = { hasDiscover: true, ready: true };
});

async function mount(q: string) {
  render(<MobileDiscoverSearchClient q={q} />);
  await act(async () => { await Promise.resolve(); });
}

describe("底栏搜索 = 豆瓣搜索", () => {
  it("底栏「搜索」Tab 指向 /m/search，而资源搜索不在底栏", () => {
    const tab = MOBILE_NAV_ITEMS.find(i => i.key === "search")!;
    expect(tab.route).toBe(MOBILE_ROUTES.search);
    // 类型上 NAV_ITEMS 的 route 联合里就没有 resource，这里再做一次运行时断言
    const routes: string[] = MOBILE_NAV_ITEMS.map(i => i.route);
    expect(routes).not.toContain(MOBILE_ROUTES.resource);
    // 资源搜索页仍归「搜索」Tab 高亮，否则底栏没有任何选中项
    expect(activeNavKey(MOBILE_ROUTES.resource)).toBe("search");
  });

  it("没有关键词时说清楚这里搜什么，不发请求也不报空态错误", async () => {
    await mount("");
    expect(screen.getByText(/按片名找片子/)).toBeTruthy();
    expect(screen.getByText(/搜索资源/)).toBeTruthy();
    expect(mockApi.doubanSearch).not.toHaveBeenCalled();
  });

  it("提交只改 URL（replace），由 URL 驱动搜索", async () => {
    await mount("");
    fireEvent.change(screen.getByLabelText("片名"), { target: { value: " 沙丘 " } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "搜索" })); });

    expect(mockRouter.replace).toHaveBeenCalledWith(discoverSearchUrl("沙丘"));
    // 提交本身不发请求（URL 变了之后由 effect 发），避免双搜
    expect(mockApi.doubanSearch).not.toHaveBeenCalled();
  });

  it("URL 带词就搜，结果渲染成发现卡片并带本地状态", async () => {
    await mount("沙丘");
    await waitFor(() => expect(screen.getByText("沙丘：预言")).toBeTruthy());
    expect(mockApi.doubanSearch).toHaveBeenCalledWith("沙丘");
    expect(mockApi.doubanSearch).toHaveBeenCalledTimes(1);
    // 本地已有的那条要标出来
    expect(screen.getByText("✓ 已有")).toBeTruthy();
  });

  it("点结果进发现详情，带真豆瓣 id 与 source=douban", async () => {
    await mount("沙丘");
    await waitFor(() => expect(screen.getByText("沙丘：预言")).toBeTruthy());
    await act(async () => { fireEvent.click(screen.getByText("沙丘：预言")); });

    const url = new URL(mockRouter.push.mock.calls.at(-1)![0], "http://x");
    expect(url.pathname).toBe(MOBILE_ROUTES.discoverDetail);
    const q = url.searchParams;
    expect(q.get(MOBILE_QUERY_KEYS.detailSource)).toBe("douban");
    expect(q.get(MOBILE_QUERY_KEYS.itemId)).toBe("35651341");
    expect(q.get(MOBILE_QUERY_KEYS.mediaType)).toBe("tv");
  });

  it("搜不到时给可操作的提示，不是空白", async () => {
    mockApi.doubanSearch.mockResolvedValue({ candidates: [] });
    await mount("不存在的片名");
    await waitFor(() => expect(screen.getByText(/没有找到「不存在的片名」/)).toBeTruthy());
  });

  it("搜索失败给错误态和重试", async () => {
    mockApi.doubanSearch.mockRejectedValue(new Error("boom"));
    await mount("沙丘");
    await waitFor(() => expect(screen.getByText(/搜索失败/)).toBeTruthy());
    expect(screen.getByRole("button", { name: "重试" })).toBeTruthy();
  });

  it("有关键词时给一个「用这个词搜资源」的出口", async () => {
    await mount("沙丘");
    await waitFor(() => expect(screen.getByText("沙丘：预言")).toBeTruthy());
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /用「沙丘」搜资源/ })); });
    expect(mockRouter.push.mock.calls.at(-1)![0]).toContain(MOBILE_ROUTES.resource);
  });

  it("没装发现插件时说明不可用，不发请求", async () => {
    mockPlugins.value = { hasDiscover: false, ready: true };
    await mount("沙丘");
    expect(screen.getByText(/没有安装发现插件/)).toBeTruthy();
    expect(mockApi.doubanSearch).not.toHaveBeenCalled();
  });
});
