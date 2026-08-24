// 锁定：组件卸载和页面隐藏后，搜索不留残余。
//
// 背景：清理原先绑在"弹窗关闭"上。移动端 /m/search 是常驻路由页，
// 没有 open=false 这个时机 —— 卸载时 SSE 连接、90s 超时定时器和在途请求
// 都会活到浏览器回收为止，超时回调还会对已卸载组件 setState。
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { useSearchState } from "@/components/search/useSearchState";
import { SEARCH_SSE_TIMEOUT_MS } from "@/lib/domain/search";
import { mockEventSourceInstances, resetMockEventSource } from "./helpers/mockEventSource";

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    getProviders: vi.fn(),
    getSearchSources: vi.fn(),
    getAIStatus: vi.fn(),
    searchPan: vi.fn(),
    searchSource: vi.fn(),
    searchStream: vi.fn(),
    searchSingle: vi.fn(),
    aiSearchRecommend: vi.fn(),
  },
}));

vi.mock("@/lib/api", () => ({ api: mockApi }));

beforeEach(() => {
  resetMockEventSource();
  Object.values(mockApi).forEach(fn => fn.mockReset());
  mockApi.getProviders.mockResolvedValue({ search: [], panSearch: [] });
  mockApi.getSearchSources.mockResolvedValue({ sources: [] });
  mockApi.getAIStatus.mockResolvedValue({ enabled: false, features: {} });
  mockApi.searchStream.mockReturnValue("/backend/api/search/stream?query=x");
  mockApi.searchSingle.mockResolvedValue({ bt_results: [] });
});

afterEach(() => {
  vi.useRealTimers();
});

function renderSearch(query: string) {
  return renderHook(() => useSearchState({
    open: true, query, defaultSavePath: "/downloads",
  }));
}

describe("搜索清理：卸载与页面隐藏", () => {
  it("卸载后 90s 超时回调不再执行，SSE 被 close 一次", async () => {
    vi.useFakeTimers();
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    const { unmount } = renderSearch("测试片名");
    // 挂载即触发 BT 主搜索，EventSource 已建立且超时已挂上
    expect(mockEventSourceInstances).toHaveLength(1);
    const es = mockEventSourceInstances[0];
    const closeSpy = vi.spyOn(es, "close");

    unmount();
    expect(closeSpy).toHaveBeenCalledTimes(1);

    // 推过整个超时窗口：不能再有任何回调触发 setState
    await act(async () => {
      vi.advanceTimersByTime(SEARCH_SSE_TIMEOUT_MS + 1000);
    });

    // 超时回调若还活着会再 close 一次并 reject，进而对已卸载组件 setState
    expect(closeSpy).toHaveBeenCalledTimes(1);
    const warned = consoleError.mock.calls.flat().join(" ");
    expect(warned).not.toMatch(/unmounted|not wrapped in act/i);
    consoleError.mockRestore();
  });

  it("pagehide 时关闭 SSE（iOS 切后台只会给这个事件）", () => {
    renderSearch("测试片名");
    const es = mockEventSourceInstances[0];
    const closeSpy = vi.spyOn(es, "close");

    act(() => { window.dispatchEvent(new Event("pagehide")); });

    expect(closeSpy).toHaveBeenCalledTimes(1);
    expect(es.readyState).toBe(2);
  });

  it("卸载后在途网盘请求的响应不写 state（不报 setState on unmounted）", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    let resolvePan!: (v: unknown) => void;
    mockApi.searchPan.mockReturnValue(new Promise(res => { resolvePan = res; }));

    const { result, unmount } = renderSearch("");
    act(() => { void result.current.doPanSearch("词"); });
    unmount();

    await act(async () => {
      resolvePan({ results: [{ title: "迟到" }], groups: {}, source_statuses: [], total: 1 });
      await Promise.resolve();
    });

    const warned = consoleError.mock.calls.flat().join(" ");
    expect(warned).not.toMatch(/unmounted|not wrapped in act/i);
    consoleError.mockRestore();
  });

  it("搜索词清空时取消在途搜索并清掉上一轮结果", async () => {
    const { result, rerender, unmount } = renderHook(
      ({ query }: { query: string }) => useSearchState({ open: true, query, defaultSavePath: "/d" }),
      { initialProps: { query: "有词" } },
    );

    const es = mockEventSourceInstances[0];
    const closeSpy = vi.spyOn(es, "close");
    // 先让流吐一条结果出来
    await act(async () => {
      es.emitMessage({ type: "source_done", source: "prowlarr", status: "done", count: 1, results: [{ title: "结果", download_url: "magnet:?xt=1", seeders: 1, size_gb: 1 }] });
    });
    expect(result.current.results).toHaveLength(1);

    await act(async () => { rerender({ query: "" }); });

    expect(closeSpy).toHaveBeenCalled();
    expect(result.current.results).toHaveLength(0);
    expect(result.current.searching).toBe(false);
    expect(result.current.error).toBe("");
    unmount();
  });
});
