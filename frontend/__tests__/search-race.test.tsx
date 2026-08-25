// 锁定：先发起的搜索响应回得晚，不得覆盖后发起的搜索结果。
//
// 背景：doPanSearch 与 doSourceSearch 原先完全没有代际门禁（只有 BT 主流程、
// fallback 和 AI 推荐有）。连续切换关键词或源时，慢的那次请求后到，
// 界面上就会显示上一次的结果 —— 用户看到的是"搜索串了"。
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { useSearchState } from "@/components/search/useSearchState";

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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(res => { resolve = res; });
  return { promise, resolve };
}

function panPayload(tag: string) {
  return {
    results: [{ title: tag, url: `https://pan.example/${tag}`, source: "quark", type: "quark" }],
    groups: {},
    source_statuses: [],
    total: 1,
  };
}

function sourcePayload(tag: string) {
  return {
    results: [{ title: tag, download_url: `magnet:?xt=${tag}`, seeders: 1, size_gb: 1 }],
    search_keywords: [tag],
    hit_keyword: tag,
  };
}

/** query 传空串，避免挂载时自动触发 BT 主搜索干扰断言 */
function renderSearch() {
  return renderHook(() => useSearchState({
    open: true, query: "", defaultSavePath: "/downloads",
  }));
}

beforeEach(() => {
  Object.values(mockApi).forEach(fn => fn.mockReset());
  mockApi.getProviders.mockResolvedValue({ search: [], panSearch: [] });
  mockApi.getSearchSources.mockResolvedValue({ sources: [] });
  mockApi.getAIStatus.mockResolvedValue({ enabled: false, features: {} });
});

describe("搜索竞态：旧响应不得覆盖新结果", () => {
  it("网盘搜索：先发起的请求后到，结果被丢弃", async () => {
    const first = deferred<any>();
    const second = deferred<any>();
    mockApi.searchPan
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);

    const { result } = renderSearch();

    // 两次搜索连续发起，第二次覆盖第一次
    act(() => { void result.current.doPanSearch("旧词"); });
    act(() => { void result.current.doPanSearch("新词"); });

    // 新的先回
    await act(async () => { second.resolve(panPayload("新结果")); });
    await waitFor(() => {
      expect(result.current.panResults[0]?.title).toBe("新结果");
    });

    // 旧的后回，必须被丢弃
    await act(async () => { first.resolve(panPayload("旧结果")); });
    expect(result.current.panResults[0]?.title).toBe("新结果");
    expect(result.current.panResults).toHaveLength(1);
  });

  it("网盘搜索：旧请求失败也不得覆盖新结果的错误态", async () => {
    const first = deferred<any>();
    const second = deferred<any>();
    mockApi.searchPan
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);

    const { result } = renderSearch();
    act(() => { void result.current.doPanSearch("旧词"); });
    act(() => { void result.current.doPanSearch("新词"); });

    await act(async () => { second.resolve(panPayload("新结果")); });
    await waitFor(() => expect(result.current.panResults).toHaveLength(1));

    await act(async () => {
      // 旧请求抛错：不能清空结果也不能显示错误
      (first as any).resolve(Promise.reject(new Error("旧请求超时")));
      await Promise.resolve();
    });
    expect(result.current.panResults[0]?.title).toBe("新结果");
    expect(result.current.error).toBe("");
  });

  it("单源搜索：先切到的源响应后到，不得写进后切到的源 Tab", async () => {
    const first = deferred<any>();
    const second = deferred<any>();
    mockApi.searchSource
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);

    const { result } = renderSearch();
    act(() => { void result.current.doSourceSearch("sourceA", "词A"); });
    act(() => { void result.current.doSourceSearch("sourceB", "词B"); });

    await act(async () => { second.resolve(sourcePayload("B 的结果")); });
    await waitFor(() => {
      expect(result.current.sourceTabStates.sourceB?.results[0]?.title).toBe("B 的结果");
    });

    await act(async () => { first.resolve(sourcePayload("A 的结果")); });
    // A 被取消：它的 Tab 仍停在发起时的空搜索中态，不该写入结果
    expect(result.current.sourceTabStates.sourceA?.results).toHaveLength(0);
    expect(result.current.sourceTabStates.sourceB?.results[0]?.title).toBe("B 的结果");
  });

  it("cancelCurrentSearch 之后的响应一律不写 state", async () => {
    const pending = deferred<any>();
    mockApi.searchPan.mockReturnValueOnce(pending.promise);

    const { result } = renderSearch();
    act(() => { void result.current.doPanSearch("词"); });
    act(() => { result.current.cancelCurrentSearch(); });

    await act(async () => { pending.resolve(panPayload("迟到的结果")); });
    expect(result.current.panResults).toHaveLength(0);
    expect(result.current.error).toBe("");
  });

  it("回归：被取消的网盘搜索必须复位 panSearching，否则搜索按钮永久禁用", async () => {
    // 收尾带代际门禁，被取消的那次走不到自己的 setPanSearching(false)。
    // 桌面 SearchHeader 的 disabled 直接读这个标志：卡住就只能关弹窗重开，
    // 而移动端路由页连这个时机都没有。
    const pending = deferred<any>();
    mockApi.searchPan.mockReturnValueOnce(pending.promise);

    const { result } = renderSearch();
    act(() => { void result.current.doPanSearch("词"); });
    await waitFor(() => expect(result.current.panSearching).toBe(true));

    act(() => { result.current.cancelCurrentSearch(); });
    expect(result.current.panSearching).toBe(false);

    // 迟到的响应也不能把它又设回 true
    await act(async () => { pending.resolve(panPayload("迟到")); });
    expect(result.current.panSearching).toBe(false);
  });

  it("回归：被取消的单源搜索必须复位该源 Tab 的 searching", async () => {
    const pending = deferred<any>();
    mockApi.searchSource.mockReturnValueOnce(pending.promise);

    const { result } = renderSearch();
    act(() => { void result.current.doSourceSearch("sourceA", "词"); });
    await waitFor(() => expect(result.current.sourceTabStates.sourceA?.searching).toBe(true));

    act(() => { result.current.cancelCurrentSearch(); });
    expect(result.current.sourceTabStates.sourceA?.searching).toBe(false);

    await act(async () => { pending.resolve(sourcePayload("迟到")); });
    expect(result.current.sourceTabStates.sourceA?.searching).toBe(false);
  });

  it("回归：新的全量搜索会先把上一轮网盘的 loading 清掉", async () => {
    const panPending = deferred<any>();
    mockApi.searchPan.mockReturnValueOnce(panPending.promise);
    mockApi.searchStream.mockReturnValue("/backend/api/search/stream?query=x");

    const { result } = renderSearch();
    act(() => { void result.current.doPanSearch("旧词"); });
    await waitFor(() => expect(result.current.panSearching).toBe(true));

    // 切回 BT Tab 回车 → beginNewSearch → abort pan 通道
    act(() => { void result.current.doSearch("新词"); });
    expect(result.current.panSearching).toBe(false);

    await act(async () => { panPending.resolve(panPayload("迟到")); });
    expect(result.current.panSearching).toBe(false);
  });

  it("重复调用 cancelCurrentSearch 不抛错（幂等）", () => {
    const { result } = renderSearch();
    expect(() => {
      act(() => {
        result.current.cancelCurrentSearch();
        result.current.cancelCurrentSearch();
      });
    }).not.toThrow();
  });
});
