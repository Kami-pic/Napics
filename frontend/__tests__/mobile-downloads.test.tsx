// 锁定下载页的四件事：完整任务不被 progress 抹掉、轮询启停、入库确认不抢跑、
// 以及需要用户介入时给出恢复入口。
//
// 断言全部走 DOM，不把 hook 返回值抓到模块变量（渲染期写外部状态是禁止的）。
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import MobileDownloadList from "@/components/mobile/MobileDownloadList";
import MobileLibraryTreeProvider from "@/components/mobile/MobileLibraryTreeProvider";
import { DOWNLOAD_POLL_INTERVAL_MS } from "@/lib/domain/download";
import { LIBRARY_CONFIRM_TIMEOUT_MS } from "@/hooks/mobile/useMobileDownloads";

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    getDownloadTasks: vi.fn(),
    getDownloadProgress: vi.fn(),
    getLibraryTree: vi.fn(),
    quickSync: vi.fn(),
  },
}));
vi.mock("@/lib/api", () => ({ api: mockApi }));

const SAVE_PATH = String.raw`\\NAS\share\视频\电视剧\某剧 S01`;

function makeTask(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: "t1",
    media_name: "某剧 S01E01",
    download_url: "magnet:?xt=1",
    save_path: SAVE_PATH,
    download_dir: "downloads/t1",
    channel: "qb",
    downloader_hash: "abc",
    category_hint: "tv",
    status: "downloading",
    progress: 0.3,
    speed: "5 MB/s",
    eta: "",
    phase: "",
    error: "",
    relocate_status: "",
    relocated_count: 0,
    is_season_pack: false,
    season_number: 1,
    created_at: "",
    updated_at: "",
    ...over,
  };
}

/** videoPaths 为空则是空库 */
function makeTree(videoPaths: string[]) {
  return {
    name: "媒体库",
    path: "",
    videos: [],
    video_count: videoPaths.length,
    has_cover: false,
    children: [
      {
        name: "电视剧",
        path: String.raw`\\NAS\share\视频\电视剧`,
        video_count: videoPaths.length,
        has_cover: false,
        children: [],
        videos: videoPaths.map(p => ({ file_path: p, file_name: "x.mkv" })),
      },
    ],
  };
}

function renderPage() {
  return render(
    <MobileLibraryTreeProvider>
      <MobileDownloadList />
    </MobileLibraryTreeProvider>,
  );
}

beforeEach(() => {
  Object.values(mockApi).forEach(fn => fn.mockReset());
  mockApi.getDownloadTasks.mockResolvedValue({ tasks: [makeTask()] });
  mockApi.getDownloadProgress.mockResolvedValue({ tasks: [] });
  mockApi.getLibraryTree.mockResolvedValue(makeTree([]));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("移动端下载任务页", () => {
  /** fake timer 必须在 render 之前装好：interval 一旦用真 timer 建立，
   *  后面再 useFakeTimers 也推不动它（这会让轮询相关断言全部假绿）。 */
  async function flush() {
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await Promise.resolve(); });
  }

  it("完整任务来自 /tasks，progress 只更新进度不抹掉其他任务", async () => {
    mockApi.getDownloadTasks.mockResolvedValue({
      tasks: [
        makeTask({ id: "t1", status: "downloading", progress: 0.3 }),
        makeTask({ id: "t2", media_name: "另一部电影", status: "completed", progress: 1 }),
      ],
    });
    // progress 只返回 downloading 子集 —— 这正是会把已完成任务抹掉的陷阱
    mockApi.getDownloadProgress.mockResolvedValue({
      tasks: [{ id: "t1", progress: 0.8, speed: "9 MB/s" }],
    });

    vi.useFakeTimers();
    renderPage();
    await flush();
    expect(screen.getByText("某剧 S01E01")).toBeInTheDocument();
    expect(screen.getByText("另一部电影")).toBeInTheDocument();

    await act(async () => { vi.advanceTimersByTime(DOWNLOAD_POLL_INTERVAL_MS); });
    await flush();

    expect(mockApi.getDownloadProgress).toHaveBeenCalled();
    expect(screen.getByText("80%")).toBeInTheDocument();
    // 回归：已完成任务不能被 progress 的子集返回抹掉
    expect(screen.getByText("另一部电影")).toBeInTheDocument();
  });

  it("全是终态时不再打 progress（它带副作用，空转让后端白做一轮对账）", async () => {
    mockApi.getDownloadTasks.mockResolvedValue({
      tasks: [makeTask({ status: "completed", progress: 1, relocate_status: "moved", relocated_count: 1 })],
    });
    mockApi.getLibraryTree.mockResolvedValue(makeTree([`${SAVE_PATH}\\某剧.mkv`]));

    vi.useFakeTimers();
    renderPage();
    await flush();
    expect(screen.getByText("已进入媒体库")).toBeInTheDocument();

    await act(async () => { vi.advanceTimersByTime(DOWNLOAD_POLL_INTERVAL_MS * 3); });
    await flush();

    expect(mockApi.getDownloadProgress).not.toHaveBeenCalled();
  });

  it("对照：有非终态任务时同样的推进确实会打 progress", async () => {
    mockApi.getDownloadTasks.mockResolvedValue({ tasks: [makeTask({ status: "downloading" })] });

    vi.useFakeTimers();
    renderPage();
    await flush();

    await act(async () => { vi.advanceTimersByTime(DOWNLOAD_POLL_INTERVAL_MS); });
    await flush();

    expect(mockApi.getDownloadProgress).toHaveBeenCalled();
  });

  it("页面切到后台时停止轮询，回到前台立刻补一次", async () => {
    mockApi.getDownloadTasks.mockResolvedValue({ tasks: [makeTask({ status: "downloading" })] });

    vi.useFakeTimers();
    renderPage();
    await flush();

    const visibility = vi.spyOn(document, "visibilityState", "get");

    visibility.mockReturnValue("hidden");
    await act(async () => { document.dispatchEvent(new Event("visibilitychange")); });
    mockApi.getDownloadProgress.mockClear();
    await act(async () => { vi.advanceTimersByTime(DOWNLOAD_POLL_INTERVAL_MS * 3); });
    await flush();
    // 轮询停了 = 对账也停了，这是预期行为
    expect(mockApi.getDownloadProgress).not.toHaveBeenCalled();

    visibility.mockReturnValue("visible");
    await act(async () => { document.dispatchEvent(new Event("visibilitychange")); });
    await flush();
    // 回前台不等下一个 tick，先补一次
    expect(mockApi.getDownloadProgress).toHaveBeenCalledTimes(1);

    visibility.mockRestore();
  });

  it("卸载后 timer 停掉，迟到的轮询响应不再引起任何请求或渲染", async () => {
    // 断言可观测行为。不要用 "setState on unmounted" 警告 ——
    // React 18.3 起不再发出，那种断言恒成立、什么都没验证。
    let releaseProgress!: (v: unknown) => void;
    mockApi.getDownloadTasks.mockResolvedValue({ tasks: [makeTask({ status: "downloading" })] });
    mockApi.getDownloadProgress.mockReturnValue(new Promise(res => { releaseProgress = res; }));

    vi.useFakeTimers();
    const { unmount } = renderPage();
    await flush();
    await act(async () => { vi.advanceTimersByTime(DOWNLOAD_POLL_INTERVAL_MS); });
    expect(mockApi.getDownloadProgress).toHaveBeenCalledTimes(1);

    unmount();
    // 卸载后 interval 必须已经停掉：再推三个周期也不该有新请求
    await act(async () => { vi.advanceTimersByTime(DOWNLOAD_POLL_INTERVAL_MS * 3); });
    expect(mockApi.getDownloadProgress).toHaveBeenCalledTimes(1);

    // 迟到的响应到达时组件已卸载，不该抛错也不该再触发请求
    await act(async () => { releaseProgress({ tasks: [{ id: "t1", progress: 0.99 }] }); });
    expect(mockApi.getDownloadProgress).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("99%")).not.toBeInTheDocument();
  });

  it("回归：往已有剧集目录追加新集时，不能因为目录里有旧集就说已入库", async () => {
    // 这是单集补全和洗版最常见的场景。判据若是"save_path 下有任何视频"，
    // 第一次渲染就会是"已进入媒体库"，而新集可能根本还没入库。
    const newEpisode = `${SAVE_PATH}\\某剧.S01E06.mkv`;
    mockApi.getDownloadTasks.mockResolvedValue({
      tasks: [makeTask({
        status: "completed", progress: 1,
        relocate_status: "moved", relocated_count: 1,
        relocated_files: [newEpisode],
        relocated_at: new Date().toISOString(),
      })],
    });
    // 库里已经有 E01–E05，但没有 E06
    mockApi.getLibraryTree.mockResolvedValue(makeTree([
      `${SAVE_PATH}\\某剧.S01E01.mkv`,
      `${SAVE_PATH}\\某剧.S01E05.mkv`,
    ]));

    renderPage();

    await waitFor(() => expect(screen.getByText("已归位 1 个文件")).toBeInTheDocument());
    expect(screen.getByText("正在确认是否进入媒体库…")).toBeInTheDocument();
    expect(screen.queryByText("已进入媒体库")).not.toBeInTheDocument();
  });

  it("新集真的入库后才显示已进入媒体库", async () => {
    const newEpisode = `${SAVE_PATH}\\某剧.S01E06.mkv`;
    mockApi.getDownloadTasks.mockResolvedValue({
      tasks: [makeTask({
        status: "completed", progress: 1,
        relocate_status: "moved", relocated_count: 1,
        relocated_files: [newEpisode],
        relocated_at: new Date().toISOString(),
      })],
    });
    mockApi.getLibraryTree.mockResolvedValue(makeTree([
      `${SAVE_PATH}\\某剧.S01E01.mkv`,
      newEpisode,
    ]));

    renderPage();
    await waitFor(() => expect(screen.getByText("已进入媒体库")).toBeInTheDocument());
  });

  it("归位的是目录（种子里是文件夹）时，按目录下有没有视频判断", async () => {
    const movedDir = `${SAVE_PATH}\\某剧 S01`;
    mockApi.getDownloadTasks.mockResolvedValue({
      tasks: [makeTask({
        status: "completed", progress: 1,
        relocate_status: "moved", relocated_count: 1,
        relocated_files: [movedDir],
        relocated_at: new Date().toISOString(),
      })],
    });
    mockApi.getLibraryTree.mockResolvedValue(makeTree([`${movedDir}\\E01.mkv`]));

    renderPage();
    await waitFor(() => expect(screen.getByText("已进入媒体库")).toBeInTheDocument());
  });

  it("库里看不到时按退避重试拉树，不是只拉一次就放弃", async () => {
    mockApi.getDownloadTasks.mockResolvedValue({
      tasks: [makeTask({
        status: "completed", progress: 1,
        relocate_status: "moved", relocated_count: 1,
        relocated_files: [`${SAVE_PATH}\\某剧.S01E06.mkv`],
        relocated_at: new Date().toISOString(),
      })],
    });
    mockApi.getLibraryTree.mockResolvedValue(makeTree([]));

    vi.useFakeTimers();
    renderPage();
    await flush();
    const afterFirst = mockApi.getLibraryTree.mock.calls.length;

    // 后端局部刷新是跑 ffprobe 的后台线程，第一次拉树时往往还没写完库。
    // 只刷一次就再也不刷的话，确认状态没有任何自愈路径。
    await act(async () => { vi.advanceTimersByTime(10_000); });
    await flush();

    expect(mockApi.getLibraryTree.mock.calls.length).toBeGreaterThan(afterFirst);
  });

  it("超时之后不再重试拉树，交给用户手动同步", async () => {
    mockApi.getDownloadTasks.mockResolvedValue({
      tasks: [makeTask({
        status: "completed", progress: 1,
        relocate_status: "moved", relocated_count: 1,
        relocated_files: [`${SAVE_PATH}\\某剧.S01E06.mkv`],
        // 归位时刻已经在超时窗口之外
        relocated_at: new Date(Date.now() - LIBRARY_CONFIRM_TIMEOUT_MS - 10_000).toISOString(),
      })],
    });
    mockApi.getLibraryTree.mockResolvedValue(makeTree([]));

    vi.useFakeTimers();
    renderPage();
    await flush();
    // fake timer 下不能用 waitFor（它自己也要推时钟），直接断言
    expect(screen.getByText(/等待入库超时/)).toBeInTheDocument();
    const afterFirst = mockApi.getLibraryTree.mock.calls.length;

    await act(async () => { vi.advanceTimersByTime(30_000); });
    await flush();

    expect(mockApi.getLibraryTree.mock.calls.length).toBe(afterFirst);
  });

  it("超时基准用后端的 relocated_at，页面重开不会重新数 60 秒", async () => {
    mockApi.getDownloadTasks.mockResolvedValue({
      tasks: [makeTask({
        status: "completed", progress: 1,
        relocate_status: "moved", relocated_count: 1,
        relocated_files: [`${SAVE_PATH}\\某剧.S01E06.mkv`],
        relocated_at: new Date(Date.now() - LIBRARY_CONFIRM_TIMEOUT_MS - 5_000).toISOString(),
      })],
    });
    mockApi.getLibraryTree.mockResolvedValue(makeTree([]));

    renderPage();
    // 刚挂载就该是超时态，而不是从头数
    await waitFor(() => expect(screen.getByText(/等待入库超时/)).toBeInTheDocument());
  });

  it("归位成功但媒体库里还没出现时，显示确认中而不是已入库", async () => {
    mockApi.getDownloadTasks.mockResolvedValue({
      tasks: [makeTask({ status: "completed", progress: 1, relocate_status: "moved", relocated_count: 2 })],
    });
    mockApi.getLibraryTree.mockResolvedValue(makeTree([]));   // 空库

    renderPage();

    await waitFor(() => expect(screen.getByText("已归位 2 个文件")).toBeInTheDocument());
    expect(screen.getByText("正在确认是否进入媒体库…")).toBeInTheDocument();
    expect(screen.queryByText("已进入媒体库")).not.toBeInTheDocument();
  });

  it("入库确认超时后提示可用快速同步恢复", async () => {
    mockApi.getDownloadTasks.mockResolvedValue({
      tasks: [makeTask({ status: "completed", progress: 1, relocate_status: "moved", relocated_count: 1 })],
    });
    mockApi.getLibraryTree.mockResolvedValue(makeTree([]));

    // 必须整条都用 fake timer：超时判定读的是 Date.now()，而 Date.now 只有在
    // fake timer 下才会随 advanceTimersByTime 前进。渲染后再切 fake timer，
    // 既推不动已建立的 interval，也推不动时钟 —— 断言会随机失败。
    vi.useFakeTimers();
    renderPage();
    await flush();
    expect(screen.getByText("正在确认是否进入媒体库…")).toBeInTheDocument();

    await act(async () => { vi.advanceTimersByTime(LIBRARY_CONFIRM_TIMEOUT_MS + 6000); });
    await flush();

    expect(screen.getByText(/等待入库超时/)).toBeInTheDocument();
  });

  it("归位因同名文件没搬动时给出可介入的提示，不显示成功", async () => {
    mockApi.getDownloadTasks.mockResolvedValue({
      tasks: [makeTask({
        status: "completed",
        progress: 1,
        relocate_status: "skipped_existing",
        relocated_count: 0,
        error: "目标目录已存在同名文件，未搬动：某剧.mkv",
      })],
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText("目标目录已有同名文件，未搬动")).toBeInTheDocument();
    });
    expect(screen.queryByText(/已归位/)).not.toBeInTheDocument();
    // 后端写的具体原因也要显示出来
    expect(screen.getByText(/某剧\.mkv/)).toBeInTheDocument();
  });

  it("lost 状态显示成正在核对，不是失败", async () => {
    mockApi.getDownloadTasks.mockResolvedValue({ tasks: [makeTask({ status: "lost" })] });
    renderPage();
    await waitFor(() => expect(screen.getByText("正在核对")).toBeInTheDocument());
    expect(screen.queryByText("失败")).not.toBeInTheDocument();
  });

  it("没有任务时显示空态，不是加载中", async () => {
    mockApi.getDownloadTasks.mockResolvedValue({ tasks: [] });
    renderPage();
    await waitFor(() => expect(screen.getByText("还没有下载任务")).toBeInTheDocument());
  });

  it("任务列表读取失败时可重试", async () => {
    mockApi.getDownloadTasks.mockRejectedValueOnce(new Error("后端没起来"));
    renderPage();
    await waitFor(() => expect(screen.getByText("下载任务读取失败")).toBeInTheDocument());

    mockApi.getDownloadTasks.mockResolvedValue({ tasks: [makeTask()] });
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    await waitFor(() => expect(screen.getByText("某剧 S01E01")).toBeInTheDocument());
  });
});

describe("快速同步恢复入口", () => {
  /** 构造一个 SSE 响应；events 为空表示流直接结束（结果未知） */
  function sseResponse(events: object[]) {
    const encoder = new TextEncoder();
    const chunks = events.map(e => encoder.encode(`data: ${JSON.stringify(e)}\n\n`));
    let i = 0;
    return {
      ok: true,
      status: 200,
      body: {
        getReader: () => ({
          read: async () => (i < chunks.length
            ? { done: false, value: chunks[i++] }
            : { done: true, value: undefined }),
          cancel: async () => {},
        }),
      },
    } as unknown as Response;
  }

  it("收到 done 才宣称成功，并刷新媒体库缓存", async () => {
    mockApi.quickSync.mockResolvedValue(sseResponse([
      { type: "status", message: "扫描文件系统..." },
      { type: "done", added: 2, removed: 0 },
    ]));

    renderPage();
    await waitFor(() => expect(screen.getByRole("button", { name: "快速同步" })).toBeEnabled());
    const treeCallsBefore = mockApi.getLibraryTree.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: "快速同步" }));

    await waitFor(() => expect(screen.getByText(/同步完成：新增 2/)).toBeInTheDocument());
    expect(mockApi.getLibraryTree.mock.calls.length).toBeGreaterThan(treeCallsBefore);
  });

  it("流断了但没收到 done 时说结果未知，不宣称成功也不刷缓存", async () => {
    mockApi.quickSync.mockResolvedValue(sseResponse([{ type: "status", message: "扫描文件系统..." }]));

    renderPage();
    await waitFor(() => expect(screen.getByRole("button", { name: "快速同步" })).toBeEnabled());
    const treeCallsBefore = mockApi.getLibraryTree.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: "快速同步" }));

    await waitFor(() => expect(screen.getByText(/结果未知/)).toBeInTheDocument());
    expect(screen.queryByText(/同步完成/)).not.toBeInTheDocument();
    expect(mockApi.getLibraryTree.mock.calls.length).toBe(treeCallsBefore);
  });

  it("HTTP 错误明确报失败", async () => {
    mockApi.quickSync.mockResolvedValue({ ok: false, status: 500 } as Response);

    renderPage();
    await waitFor(() => expect(screen.getByRole("button", { name: "快速同步" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "快速同步" }));

    await waitFor(() => expect(screen.getByText(/HTTP 500/)).toBeInTheDocument());
  });

  it("同步进行中按钮禁用，重复点击不会叠加请求", async () => {
    let release!: (v: unknown) => void;
    mockApi.quickSync.mockReturnValue(new Promise(res => { release = res; }));

    renderPage();
    await waitFor(() => expect(screen.getByRole("button", { name: "快速同步" })).toBeEnabled());

    fireEvent.click(screen.getByRole("button", { name: "快速同步" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "同步中…" })).toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "同步中…" }));

    expect(mockApi.quickSync).toHaveBeenCalledTimes(1);
    await act(async () => { release(sseResponse([{ type: "done", added: 0, removed: 0 }])); });
  });
});
