// 锁定整树缓存的行为：一次会话一次请求，显式 reload 才重拉，并发不叠加。
//
// /library/tree 返回整棵目录树和所有视频对象，且经 /backend 代理时 gzip 不生效。
// 手机切 Tab 会重挂载页面组件，每个页面自己拉一次在 NAS 链路上是纯浪费。
//
// 断言全部走 DOM：把 hook 返回值抓到模块变量里会在渲染期写外部状态，
// 那是 react-hooks 规则明确禁止的写法。
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useEffect } from "react";

import MobileLibraryTreeProvider, {
  useMobileLibraryTree,
} from "@/components/mobile/MobileLibraryTreeProvider";

const { mockApi } = vi.hoisted(() => ({
  mockApi: { getLibraryTree: vi.fn() },
}));
vi.mock("@/lib/api", () => ({ api: mockApi }));

const VIDEO_A = String.raw`\\NAS\share\视频\电影\教父 The Godfather (1972)\教父.mkv`;
const VIDEO_B = String.raw`\\NAS\share\视频\电视剧\奇怪的律师禹英禑\S01E01.mkv`;

/** 视频只放在第三层，顺便验证 hasVideoPath 真的做了全树递归 */
function makeTree(videoPaths: string[]) {
  return {
    name: "媒体库",
    path: "",
    videos: [],
    video_count: videoPaths.length,
    has_cover: false,
    children: [
      {
        name: "电影",
        path: String.raw`\\NAS\share\视频\电影`,
        video_count: videoPaths.length,
        has_cover: false,
        videos: [],
        children: [
          {
            name: "深层目录",
            path: String.raw`\\NAS\share\视频\电影\深层`,
            video_count: videoPaths.length,
            has_cover: false,
            children: [],
            videos: videoPaths.map(p => ({ file_path: p, file_name: "x.mkv" })),
          },
        ],
      },
    ],
  };
}

function Probe({ label, probePath }: { label: string; probePath?: string }) {
  const { ready, tree, version, loadFailed, reload, ensureLoaded, hasVideoPath } = useMobileLibraryTree();
  // 需要树的页面必须自己触发加载（Provider 不自动拉，否则 /m/search 也会白拉）
  useEffect(() => { ensureLoaded(); }, [ensureLoaded]);
  return (
    <div>
      <div data-testid={label}>
        {[
          ready ? "ready" : "loading",
          tree?.name ?? "无树",
          `v${version}`,
          loadFailed ? "failed" : "ok",
          probePath === undefined ? "-" : hasVideoPath(probePath) ? "命中" : "未命中",
        ].join("|")}
      </div>
      <button type="button" data-testid={`${label}-reload`} onClick={() => void reload()}>
        重载
      </button>
    </div>
  );
}

function renderProvider(children: React.ReactNode) {
  return render(<MobileLibraryTreeProvider>{children}</MobileLibraryTreeProvider>);
}

beforeEach(() => {
  mockApi.getLibraryTree.mockReset();
  mockApi.getLibraryTree.mockResolvedValue(makeTree([VIDEO_A]));
});

describe("移动端整树缓存", () => {
  it("两个消费者共享一份树，整树只请求一次", async () => {
    renderProvider(<><Probe label="a" /><Probe label="b" /></>);

    await waitFor(() => {
      expect(screen.getByTestId("a")).toHaveTextContent("ready|媒体库|v1|ok");
      expect(screen.getByTestId("b")).toHaveTextContent("ready|媒体库|v1|ok");
    });
    expect(mockApi.getLibraryTree).toHaveBeenCalledTimes(1);
  });

  it("hasVideoPath 能查到深层节点里的视频", async () => {
    renderProvider(<Probe label="hit" probePath={VIDEO_A} />);
    await waitFor(() => expect(screen.getByTestId("hit")).toHaveTextContent("命中"));
  });

  it("不在库里的路径返回未命中", async () => {
    renderProvider(<Probe label="miss" probePath={VIDEO_B} />);
    await waitFor(() => expect(screen.getByTestId("miss")).toHaveTextContent("ready"));
    expect(screen.getByTestId("miss")).toHaveTextContent("未命中");
  });

  it("空路径不算命中", async () => {
    renderProvider(<Probe label="empty" probePath="" />);
    await waitFor(() => expect(screen.getByTestId("empty")).toHaveTextContent("ready"));
    expect(screen.getByTestId("empty")).toHaveTextContent("未命中");
  });

  it("reload 后能看到新入库的视频，version 递增", async () => {
    renderProvider(<Probe label="a" probePath={VIDEO_B} />);
    await waitFor(() => expect(screen.getByTestId("a")).toHaveTextContent("v1"));
    expect(screen.getByTestId("a")).toHaveTextContent("未命中");

    // 模拟归位入库后重新读树
    mockApi.getLibraryTree.mockResolvedValue(makeTree([VIDEO_A, VIDEO_B]));
    fireEvent.click(screen.getByTestId("a-reload"));

    await waitFor(() => expect(screen.getByTestId("a")).toHaveTextContent("v2"));
    expect(screen.getByTestId("a")).toHaveTextContent("命中");
    expect(mockApi.getLibraryTree).toHaveBeenCalledTimes(2);
  });

  it("并发 reload 只发一个请求（重复点同步不该叠加整树请求）", async () => {
    let resolveTree!: (v: unknown) => void;
    mockApi.getLibraryTree.mockReturnValue(new Promise(res => { resolveTree = res; }));

    renderProvider(<Probe label="a" />);
    // 初次加载还在途中时再连点两次
    fireEvent.click(screen.getByTestId("a-reload"));
    fireEvent.click(screen.getByTestId("a-reload"));
    await act(async () => { resolveTree(makeTree([VIDEO_A])); });

    await waitFor(() => expect(screen.getByTestId("a")).toHaveTextContent("ready"));
    expect(mockApi.getLibraryTree).toHaveBeenCalledTimes(1);
  });

  it("请求失败时标记 failed 并进入 ready，不卡在加载态", async () => {
    mockApi.getLibraryTree.mockRejectedValue(new Error("后端没起来"));

    renderProvider(<Probe label="a" probePath={VIDEO_A} />);

    await waitFor(() => {
      expect(screen.getByTestId("a")).toHaveTextContent("ready|无树|v0|failed|未命中");
    });
  });

  it("失败后 reload 成功能恢复", async () => {
    mockApi.getLibraryTree.mockRejectedValueOnce(new Error("超时"));
    renderProvider(<Probe label="a" probePath={VIDEO_A} />);
    await waitFor(() => expect(screen.getByTestId("a")).toHaveTextContent("failed"));

    mockApi.getLibraryTree.mockResolvedValue(makeTree([VIDEO_A]));
    fireEvent.click(screen.getByTestId("a-reload"));

    await waitFor(() => expect(screen.getByTestId("a")).toHaveTextContent("ok|命中"));
  });

  it("没有消费者调 ensureLoaded 时不发请求（/m/search、/m/play 不该白拉整树）", async () => {
    function Bystander() {
      // 只读状态，不调 ensureLoaded
      const { ready } = useMobileLibraryTree();
      return <div data-testid="bystander">{ready ? "ready" : "idle"}</div>;
    }
    renderProvider(<Bystander />);
    await act(async () => { await Promise.resolve(); });

    expect(mockApi.getLibraryTree).not.toHaveBeenCalled();
    expect(screen.getByTestId("bystander")).toHaveTextContent("idle");
  });

  it("ensureLoaded 幂等：多个消费者都调也只请求一次", async () => {
    renderProvider(<><Probe label="a" /><Probe label="b" /></>);
    await waitFor(() => expect(screen.getByTestId("a")).toHaveTextContent("ready"));
    expect(mockApi.getLibraryTree).toHaveBeenCalledTimes(1);
  });

  it("在 Provider 外使用会明确报错", () => {
    function Outside() {
      useMobileLibraryTree();
      return null;
    }
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Outside />)).toThrow(/MobileProviders/);
    consoleError.mockRestore();
  });
});
