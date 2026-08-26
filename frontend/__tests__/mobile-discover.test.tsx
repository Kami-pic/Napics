// 移动端发现：榜单页（固定分页 + 每 tab 缓存 + 本地状态角标）与发现详情（两个出口）。
//
// 重点锁三件容易回归的事：
// 1. 分页量固定，不跟视口列数联动 —— 转屏不能清缓存重拉。
// 2. 卡片点击进发现详情，不直接跳搜索。
// 3. 本地状态角标与桌面同一份判定（lib/discoverStatus）。
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import MobileDiscoverClient from "@/components/mobile/MobileDiscoverClient";
import MobileDiscoverDetailClient from "@/components/mobile/MobileDiscoverDetailClient";
import { RECOMMEND_TABS } from "@/components/media/discoverUtils";
import { MOBILE_DISCOVER_PAGE_SIZE } from "@/lib/mobile/mobileConstants";
import {
  MOBILE_QUERY_KEYS,
  MOBILE_ROUTES,
  discoverUrl,
  libraryUrl,
} from "@/lib/mobile/mobileRouteUtils";

const { mockRouter } = vi.hoisted(() => ({
  mockRouter: { push: vi.fn(), replace: vi.fn(), back: vi.fn() },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/m",
}));

const { mockPlugins } = vi.hoisted(() => ({
  mockPlugins: { value: { hasDiscover: true, ready: true } as Record<string, unknown> },
}));
vi.mock("@/components/mobile/MobileProviders", () => ({
  useMobilePlugins: () => mockPlugins.value,
}));

const { mockApi } = vi.hoisted(() => ({
  mockApi: { discoverRecommend: vi.fn(), mediaInfo: vi.fn() },
}));
vi.mock("@/lib/api", () => ({ api: mockApi }));

/** 后端原始形状（前端会经 normalizeItem 转成 DoubanHotItem） */
function rawItem(n: number, over: Record<string, unknown> = {}) {
  return {
    douban_id: `id-${n}`,
    title: `片子 ${n}`,
    year: "2024",
    rating: 8.1,
    poster_url: `https://img1.doubanio.com/view/${n}.jpg`,
    media_type: n % 2 === 0 ? "movie" : "tv",
    local_status: "none",
    ...over,
  };
}

function page(count: number, offset = 0, over: Record<string, unknown> = {}) {
  return { items: Array.from({ length: count }, (_, i) => rawItem(offset + i, over)) };
}

const FULL_PAGE = MOBILE_DISCOVER_PAGE_SIZE;
const FIRST_TAB = RECOMMEND_TABS[0].key;

beforeEach(() => {
  mockRouter.push.mockReset();
  mockRouter.replace.mockReset();
  mockApi.discoverRecommend.mockReset();
  mockApi.mediaInfo.mockReset();
  mockPlugins.value = { hasDiscover: true, ready: true };
  mockApi.discoverRecommend.mockResolvedValue(page(FULL_PAGE));
});

async function mountList(initialTab?: string) {
  render(<MobileDiscoverClient initialTab={initialTab} />);
  await waitFor(() => expect(mockApi.discoverRecommend).toHaveBeenCalled());
  await act(async () => { await Promise.resolve(); });
}

describe("榜单加载与分页", () => {
  it("首屏用固定分页量请求第一个榜单", async () => {
    await mountList();
    expect(mockApi.discoverRecommend).toHaveBeenCalledWith(FIRST_TAB, 0, FULL_PAGE);
    expect(mockApi.discoverRecommend).toHaveBeenCalledTimes(1);
  });

  it("加载更多按 offset 翻页并追加，不重复条目", async () => {
    mockApi.discoverRecommend.mockResolvedValueOnce(page(FULL_PAGE, 0));
    mockApi.discoverRecommend.mockResolvedValueOnce(page(FULL_PAGE, FULL_PAGE));
    await mountList();

    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "加载更多" })); });
    expect(mockApi.discoverRecommend).toHaveBeenLastCalledWith(FIRST_TAB, FULL_PAGE, FULL_PAGE);
    expect(screen.getByText(`片子 ${FULL_PAGE}`)).toBeTruthy();
    expect(screen.getAllByText("片子 0").length).toBe(1);
  });

  it("没有 id 的源按「片名+年份」去重，同名不同年不会被吞掉", async () => {
    // 有海报才不会渲染文字占位，标题就只出现在卡片标题一处
    mockApi.discoverRecommend.mockResolvedValue({
      items: [
        rawItem(1, { title: "无间道", year: "2002", douban_id: "" }),
        rawItem(2, { title: "无间道", year: "2023", douban_id: "" }),
      ],
    });
    await mountList();
    expect(screen.getAllByText("无间道").length).toBe(2);
    // 对照：年份不同的两条都在
    expect(screen.getByText(/2002/)).toBeTruthy();
    expect(screen.getByText(/2023/)).toBeTruthy();
  });

  it("下一页全是重复条目时不再给「加载更多」", async () => {
    mockApi.discoverRecommend.mockResolvedValue(page(FULL_PAGE, 0));
    await mountList();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "加载更多" })); });
    expect(screen.queryByRole("button", { name: "加载更多" })).toBeNull();
  });

  it("返回条数不足一页 → 没有下一页", async () => {
    mockApi.discoverRecommend.mockResolvedValue(page(FULL_PAGE - 5));
    await mountList();
    expect(screen.queryByRole("button", { name: "加载更多" })).toBeNull();
  });

  it("追加失败保留已有内容，只提示可重试", async () => {
    mockApi.discoverRecommend.mockResolvedValueOnce(page(FULL_PAGE, 0));
    mockApi.discoverRecommend.mockRejectedValueOnce(new Error("boom"));
    await mountList();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "加载更多" })); });

    expect(screen.getByText(/加载更多失败/)).toBeTruthy();
    expect(screen.getByText("片子 0")).toBeTruthy();
    expect(screen.getByRole("button", { name: "加载更多" })).toBeTruthy();
  });

  it("首屏失败给错误态和重试，重试成功后正常显示", async () => {
    mockApi.discoverRecommend.mockRejectedValueOnce(new Error("boom"));
    await mountList();
    await waitFor(() => expect(screen.getByText(/榜单加载失败/)).toBeTruthy());

    mockApi.discoverRecommend.mockResolvedValueOnce(page(3));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "重试" })); });
    expect(screen.getByText("片子 0")).toBeTruthy();
  });

  it("空榜单说清楚可以换一个，不是白屏", async () => {
    mockApi.discoverRecommend.mockResolvedValue({ items: [] });
    await mountList();
    expect(screen.getByText(/换一个试试/)).toBeTruthy();
  });
});

describe("tab 切换", () => {
  it("切 tab 只拉一次，切回来用缓存不重发", async () => {
    await mountList();
    const second = RECOMMEND_TABS[1];

    await act(async () => { fireEvent.click(screen.getByRole("tab", { name: second.label })); });
    expect(mockApi.discoverRecommend).toHaveBeenCalledWith(second.key, 0, FULL_PAGE);
    const callsAfterSwitch = mockApi.discoverRecommend.mock.calls.length;

    await act(async () => { fireEvent.click(screen.getByRole("tab", { name: RECOMMEND_TABS[0].label })); });
    expect(mockApi.discoverRecommend.mock.calls.length).toBe(callsAfterSwitch);
  });

  it("tab 写进 URL 且用 replace（不往历史栈堆层）", async () => {
    await mountList();
    const second = RECOMMEND_TABS[1];
    await act(async () => { fireEvent.click(screen.getByRole("tab", { name: second.label })); });

    expect(mockRouter.replace).toHaveBeenCalledWith(discoverUrl(second.key));
    expect(mockRouter.push).not.toHaveBeenCalled();
  });

  it("URL 带 tab 时首屏就加载那个榜单", async () => {
    const target = RECOMMEND_TABS[2];
    await mountList(target.key);
    expect(mockApi.discoverRecommend).toHaveBeenCalledWith(target.key, 0, FULL_PAGE);
    expect(screen.getByRole("tab", { selected: true }).textContent).toBe(target.label);
  });

  it("URL 里是未知 tab 时退回第一个榜单，不发无效请求", async () => {
    await mountList("不存在的榜单");
    expect(mockApi.discoverRecommend).toHaveBeenCalledWith(FIRST_TAB, 0, FULL_PAGE);
  });

  it("上一个 tab 的迟到响应不会显示在当前 tab 上", async () => {
    let resolveFirst: (v: unknown) => void = () => {};
    mockApi.discoverRecommend.mockReturnValueOnce(new Promise(r => { resolveFirst = r; }));
    mockApi.discoverRecommend.mockResolvedValueOnce({ items: [rawItem(99, { title: "第二个榜单的片子" })] });

    render(<MobileDiscoverClient />);
    const second = RECOMMEND_TABS[1];
    await act(async () => { fireEvent.click(screen.getByRole("tab", { name: second.label })); });
    await waitFor(() => expect(screen.getByText("第二个榜单的片子")).toBeTruthy());

    await act(async () => { resolveFirst(page(FULL_PAGE, 0)); });
    expect(screen.queryByText("片子 0")).toBeNull();
    expect(screen.getByText("第二个榜单的片子")).toBeTruthy();
  });

  it("周榜是前端合成的伪 tab：并发拉华语+全球两个源，且不分页", async () => {
    const weekly = RECOMMEND_TABS.find(t => t.key === "weekly_combined")!;
    mockApi.discoverRecommend.mockResolvedValue(page(FULL_PAGE, 0));
    await mountList();
    mockApi.discoverRecommend.mockClear();

    await act(async () => { fireEvent.click(screen.getByRole("tab", { name: weekly.label })); });
    const sources = mockApi.discoverRecommend.mock.calls.map(c => c[0]);
    expect(sources).toContain("douban_weekly_chinese");
    expect(sources).toContain("douban_weekly_global");
    expect(sources).not.toContain("weekly_combined");
    expect(screen.queryByRole("button", { name: "加载更多" })).toBeNull();
  });

  it("周榜分两段显示，排名在段内各自从 1 开始", async () => {
    const weekly = RECOMMEND_TABS.find(t => t.key === "weekly_combined")!;
    // 两个源各 3 条。首尾相接的话全球榜第 1 名会被标成第 4 名
    mockApi.discoverRecommend.mockImplementation((source: string) => Promise.resolve({
      items: source === "douban_weekly_chinese"
        ? [rawItem(1, { title: "华语第一" }), rawItem(2, { title: "华语第二" }), rawItem(3, { title: "华语第三" })]
        : [rawItem(4, { title: "全球第一" }), rawItem(5, { title: "全球第二" }), rawItem(6, { title: "全球第三" })],
    }));
    await mountList(weekly.key);

    expect(screen.getByRole("heading", { name: "华语剧集周榜" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "全球剧集周榜" })).toBeTruthy();
    // 两段各有一个"1"，说明位次是段内计算的
    expect(screen.getAllByText("1").length).toBe(2);
    expect(screen.queryByText("4")).toBeNull();
  });
});

describe("横竖屏切换", () => {
  it("视口宽度变化不触发任何新请求，也不清空已加载内容", async () => {
    await mountList();
    const before = mockApi.discoverRecommend.mock.calls.length;

    await act(async () => {
      Object.defineProperty(window, "innerWidth", { value: 900, configurable: true });
      Object.defineProperty(window, "innerHeight", { value: 400, configurable: true });
      window.dispatchEvent(new Event("resize"));
      window.dispatchEvent(new Event("orientationchange"));
    });

    expect(mockApi.discoverRecommend.mock.calls.length).toBe(before);
    expect(screen.getByText("片子 0")).toBeTruthy();
  });
});

describe("本地状态角标", () => {
  it("已有 / 可升级 / 未拥有三态，与桌面同一套文案", async () => {
    mockApi.discoverRecommend.mockResolvedValue({
      items: [
        rawItem(1, { title: "已入库的", local_status: "owned_high", local_folder: "D:\\影视\\已入库的 (2024)" }),
        rawItem(2, { title: "画质低的", local_status: "owned_low", local_folder: "D:\\影视\\画质低的 (2024)" }),
        rawItem(3, { title: "没有的", local_status: "none" }),
      ],
    });
    await mountList();

    expect(screen.getByText("✓ 已有")).toBeTruthy();
    expect(screen.getByText("↑ 可升级")).toBeTruthy();
    // 未拥有不加任何角标，也不写"未拥有"这种噪音
    expect(screen.queryByText(/未拥有/)).toBeNull();
  });

  it("混合类型榜单标电影/剧集，单类型榜单不标", async () => {
    mockApi.discoverRecommend.mockResolvedValue({ items: [rawItem(2, { title: "一部电影", media_type: "movie" })] });
    await mountList("combined");   // combined 的 mediaType 是 mixed
    expect(screen.getByText(/电影 ·/)).toBeTruthy();
  });
});

describe("卡片点击", () => {
  it("进发现详情而不是直接跳搜索，并带上完整上下文", async () => {
    mockApi.discoverRecommend.mockResolvedValue({
      items: [rawItem(1, {
        title: "三体 第一季",
        media_type: "tv",
        local_status: "owned_low",
        local_folder: "D:\\影视\\三体 (2024)",
        clean_name_cn: "三体",
        clean_name_en: "Three-Body",
      })],
    });
    await mountList("douban_tv_hot");

    await act(async () => { fireEvent.click(screen.getByText("三体 第一季")); });
    const url = new URL(mockRouter.push.mock.calls.at(-1)![0], "http://x");
    expect(url.pathname).toBe(MOBILE_ROUTES.discoverDetail);

    const q = url.searchParams;
    expect(q.get(MOBILE_QUERY_KEYS.title)).toBe("三体 第一季");
    expect(q.get(MOBILE_QUERY_KEYS.mediaType)).toBe("tv");
    expect(q.get(MOBILE_QUERY_KEYS.cnName)).toBe("三体");
    expect(q.get(MOBILE_QUERY_KEYS.enName)).toBe("Three-Body");
    expect(q.get(MOBILE_QUERY_KEYS.localStatus)).toBe("owned_low");
    expect(q.get(MOBILE_QUERY_KEYS.localFolder)).toBe("D:\\影视\\三体 (2024)");
    // 从哪个榜单进来的要记住
    expect(q.get(MOBILE_QUERY_KEYS.tab)).toBe("douban_tv_hot");
  });

  it("综合推荐不传条目 id：它是混合来源，id 未必属于该榜单的评分源", async () => {
    // combined 的条目可能来自 TMDB（normalizeItem 会把 tmdb_id 填进 douban_id），
    // 拿这种 id 去按豆瓣 id 直查会命中另一部片子
    mockApi.discoverRecommend.mockResolvedValue({
      items: [rawItem(1, { title: "综合榜里的片", douban_id: "1061474" })],
    });
    await mountList("combined");
    await act(async () => { fireEvent.click(screen.getByText("综合榜里的片")); });

    const q = new URL(mockRouter.push.mock.calls.at(-1)![0], "http://x").searchParams;
    expect(q.get(MOBILE_QUERY_KEYS.detailSource)).toBe("douban");
    expect(q.get(MOBILE_QUERY_KEYS.itemId)).toBeNull();
  });

  it("单一来源的榜单照常传 id", async () => {
    mockApi.discoverRecommend.mockResolvedValue({
      items: [rawItem(1, { title: "豆瓣榜里的片", douban_id: "35651341" })],
    });
    await mountList("douban_tv_hot");
    await act(async () => { fireEvent.click(screen.getByText("豆瓣榜里的片")); });

    const q = new URL(mockRouter.push.mock.calls.at(-1)![0], "http://x").searchParams;
    expect(q.get(MOBILE_QUERY_KEYS.itemId)).toBe("35651341");
  });

  it("详情数据源跟随榜单的评分源", async () => {
    mockApi.discoverRecommend.mockResolvedValue({ items: [rawItem(1, { title: "某番" })] });
    await mountList("bangumi_calendar");
    await act(async () => { fireEvent.click(screen.getByText("某番")); });

    const url = new URL(mockRouter.push.mock.calls.at(-1)![0], "http://x");
    expect(url.searchParams.get(MOBILE_QUERY_KEYS.detailSource)).toBe("bangumi");
  });
});

describe("插件不可用", () => {
  it("没装 feature-discover 时给出口，不发请求", async () => {
    mockPlugins.value = { hasDiscover: false, ready: true };
    render(<MobileDiscoverClient />);
    await act(async () => { await Promise.resolve(); });

    expect(screen.getByText(/没有安装发现插件/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "直接搜资源" }).getAttribute("href")).toBe(MOBILE_ROUTES.resource);
    expect(mockApi.discoverRecommend).not.toHaveBeenCalled();
  });
});

// ── 发现详情 ──

const DETAIL_FOUND = {
  found: true,
  title: "沙丘 3",
  original_title: "Dune: Part Three",
  year: "2026",
  poster_url: "https://image.tmdb.org/t/p/w500/dune3.jpg",
  overview: "厄崔迪家族的故事继续。",
  genres: ["科幻", "冒险"],
  countries: ["美国"],
  runtime: 165,
  director: "丹尼斯·维伦纽瓦",
  cast: ["提莫西·柴勒梅德", "赞达亚"],
  ratings: { douban: 8.2, tmdb: 7.9 },
};

async function mountDetail(over: Record<string, unknown> = {}) {
  render(<MobileDiscoverDetailClient query={{ title: "沙丘 3", year: "2026", mediaType: "movie", source: "tmdb", id: "1", tab: "combined", ...over } as never} />);
  await act(async () => { await Promise.resolve(); });
}

describe("发现详情", () => {
  it("按桌面同一组参数请求 /media/info，且只请求一次", async () => {
    mockApi.mediaInfo.mockResolvedValue(DETAIL_FOUND);
    await mountDetail({ title: "详情参数用片", subtitle: "Some Sub" });

    await waitFor(() => expect(mockApi.mediaInfo).toHaveBeenCalled());
    expect(mockApi.mediaInfo).toHaveBeenCalledWith("详情参数用片", "2026", "movie", "Some Sub", "tmdb", "1");
    expect(mockApi.mediaInfo).toHaveBeenCalledTimes(1);
  });

  it("展示三家评分、规格与简介", async () => {
    mockApi.mediaInfo.mockResolvedValue(DETAIL_FOUND);
    await mountDetail({ title: "评分展示用片" });
    await waitFor(() => expect(screen.getByText(/厄崔迪家族/)).toBeTruthy());

    expect(screen.getByText("8.2")).toBeTruthy();
    expect(screen.getByText("7.9")).toBeTruthy();
    expect(screen.getByText(/165 分钟/)).toBeTruthy();
    expect(screen.getByText("丹尼斯·维伦纽瓦")).toBeTruthy();
  });

  it("详情拉不到时不整页报错，仍能搜索资源", async () => {
    mockApi.mediaInfo.mockRejectedValue(new Error("boom"));
    await mountDetail({ title: "拉不到详情的片", cnName: "拉不到详情的片" });
    await waitFor(() => expect(screen.getByText(/仍可直接搜索资源/)).toBeTruthy());
    expect(screen.getByRole("button", { name: /搜索资源/ })).toBeTruthy();
  });

  it("三个源都没匹配到时的文案与请求失败不同", async () => {
    mockApi.mediaInfo.mockResolvedValue({ found: false });
    await mountDetail({ title: "没人认识的片" });
    await waitFor(() => expect(screen.getByText(/三个元数据源都没匹配到/)).toBeTruthy());
  });

  it("搜索资源带三种清洗名与媒体类型", async () => {
    mockApi.mediaInfo.mockResolvedValue({ ...DETAIL_FOUND, title: "跳搜索用片" });
    await mountDetail({
      title: "跳搜索用片",
      mediaType: "tv",
      cnName: "跳搜索",
      enName: "Jump Search",
      originalName: "ジャンプ",
    });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /搜索资源/ })); });

    const url = new URL(mockRouter.push.mock.calls.at(-1)![0], "http://x");
    expect(url.pathname).toBe(MOBILE_ROUTES.resource);
    const q = url.searchParams;
    expect(q.get(MOBILE_QUERY_KEYS.query)).toBe("跳搜索");
    expect(q.get(MOBILE_QUERY_KEYS.cnName)).toBe("跳搜索");
    expect(q.get(MOBILE_QUERY_KEYS.enName)).toBe("Jump Search");
    expect(q.get(MOBILE_QUERY_KEYS.originalName)).toBe("ジャンプ");
    expect(q.get(MOBILE_QUERY_KEYS.mediaType)).toBe("tv");
  });

  it("本地已有时给「查看本地」，跳到该文件夹", async () => {
    mockApi.mediaInfo.mockResolvedValue({ ...DETAIL_FOUND, title: "本地有的片" });
    const folder = String.raw`\\NAS\share\视频\电影\本地有的片 (2024)`;
    await mountDetail({ title: "本地有的片", localStatus: "owned_low", localFolder: folder });

    const btn = screen.getByRole("button", { name: "本地已有（可升级）" });
    await act(async () => { fireEvent.click(btn); });
    expect(mockRouter.push).toHaveBeenCalledWith(libraryUrl(folder));
  });

  it("本地没有时不出现「查看本地」", async () => {
    mockApi.mediaInfo.mockResolvedValue({ ...DETAIL_FOUND, title: "本地没有的片" });
    await mountDetail({ title: "本地没有的片" });
    await waitFor(() => expect(screen.getByRole("button", { name: /搜索资源/ })).toBeTruthy());
    expect(screen.queryByRole("button", { name: /查看本地/ })).toBeNull();
    // 内容区里只有"搜索资源"一个按钮
    expect(within(screen.getByRole("main")).getAllByRole("button").length).toBe(1);
  });

  it("返回回到来源榜单", async () => {
    mockApi.mediaInfo.mockResolvedValue({ ...DETAIL_FOUND, title: "返回用片" });
    await mountDetail({ title: "返回用片", tab: "douban_animation" });
    await act(async () => { fireEvent.click(screen.getByLabelText("返回")); });
    expect(mockRouter.push).toHaveBeenCalledWith(discoverUrl("douban_animation"));
  });

  it("详情还在路上时页面已经可用：标题、海报、两个出口都不等它", async () => {
    // /media/info 冷缓存实测 6 秒起，整页 loading 会让不依赖详情的出口也点不到
    mockApi.mediaInfo.mockReturnValue(new Promise(() => {}));
    render(<MobileDiscoverDetailClient query={{
      title: "还在加载的片", year: "2026", source: "tmdb", tab: "combined",
      cover: "https://img9.doubanio.com/view/photo/x.jpg",
      localStatus: "owned_high", localFolder: "D:\\影视\\还在加载的片",
    } as never} />);
    await act(async () => { await Promise.resolve(); });

    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("还在加载的片");
    expect(screen.getByText("正在读取影片信息…")).toBeTruthy();
    // 卡片那张海报先顶上，不是空白框
    expect(document.querySelector("img")?.getAttribute("src")).toContain("doubanio.com");

    // 两个出口立刻可用
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /搜索资源/ })); });
    expect(mockRouter.push.mock.calls.at(-1)![0]).toContain(MOBILE_ROUTES.resource);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "查看本地" })); });
    expect(mockRouter.push).toHaveBeenLastCalledWith(libraryUrl("D:\\影视\\还在加载的片"));
  });

  it("详情请求一直不返回时超时收场，搜索资源仍可用", async () => {
    // fake timer 必须在 render 之前装：先 render 再装推不动已建立的 timer
    vi.useFakeTimers();
    mockApi.mediaInfo.mockReturnValue(new Promise(() => {}));   // 永不 resolve
    render(<MobileDiscoverDetailClient query={{ title: "卡住的片", year: "2026", source: "tmdb" } as never} />);
    await act(async () => { await Promise.resolve(); });

    expect(screen.getByText("正在读取影片信息…")).toBeTruthy();
    await act(async () => { vi.advanceTimersByTime(15_000); });

    expect(screen.getByText(/仍可直接搜索资源/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /搜索资源/ })).toBeTruthy();
    vi.useRealTimers();
  });

  it("缓存命中时直接显示，不再打 /media/info", async () => {
    mockApi.mediaInfo.mockResolvedValue({ ...DETAIL_FOUND, title: "会被缓存的片", overview: "缓存过的简介" });
    await mountDetail({ title: "会被缓存的片" });
    await waitFor(() => expect(screen.getByText("缓存过的简介")).toBeTruthy());

    // 卸载重挂：同一个 title_year_source 应该命中 localStorage 缓存
    cleanup();
    mockApi.mediaInfo.mockClear();
    await mountDetail({ title: "会被缓存的片" });
    expect(screen.getByText("缓存过的简介")).toBeTruthy();
    expect(mockApi.mediaInfo).not.toHaveBeenCalled();
  });

  it("缺标题时明确提示并给出口，不发请求", async () => {
    await mountDetail({ title: "" });
    expect(screen.getByText(/缺少影片信息/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "回发现" })).toBeTruthy();
    expect(mockApi.mediaInfo).not.toHaveBeenCalled();
  });
});

describe("胶囊条无障碍", () => {
  it("tablist 与内容区配对（aria-controls ↔ tabpanel）", async () => {
    await mountList();
    const selected = screen.getByRole("tab", { selected: true });
    const panelId = selected.getAttribute("aria-controls");
    expect(panelId).toBeTruthy();
    expect(document.getElementById(panelId!)?.getAttribute("role")).toBe("tabpanel");
  });

  it("roving tabindex：只有选中项可 Tab 落点", async () => {
    await mountList();
    expect(screen.getByRole("tab", { selected: true }).getAttribute("tabindex")).toBe("0");
    const others = screen.getAllByRole("tab").filter(t => t.getAttribute("aria-selected") !== "true");
    for (const tab of others) expect(tab.getAttribute("tabindex")).toBe("-1");
  });

  it("左右方向键换榜单，到头环绕", async () => {
    await mountList();
    const list = screen.getByRole("tablist");

    await act(async () => { fireEvent.keyDown(list, { key: "ArrowRight" }); });
    expect(screen.getByRole("tab", { selected: true }).textContent).toBe(RECOMMEND_TABS[1].label);

    // 从第一个往左 → 环绕到最后一个
    await act(async () => { fireEvent.keyDown(list, { key: "ArrowLeft" }); });
    await act(async () => { fireEvent.keyDown(list, { key: "ArrowLeft" }); });
    expect(screen.getByRole("tab", { selected: true }).textContent)
      .toBe(RECOMMEND_TABS[RECOMMEND_TABS.length - 1].label);
  });
});
