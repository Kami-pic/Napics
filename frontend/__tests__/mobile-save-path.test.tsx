// 锁定保存路径三段交互：默认值预填、全屏 sheet 逐级进入并回填、手输带可达提示。
//
// 触屏关键点：桌面 FolderPicker 每行的「选这个」是 opacity-0 group-hover:opacity-100，
// 手机上没有 hover 根本点不到，所以移动端整行可点 + 独立的「用这里」按钮。
// checkPath 失败只提示不阻止提交 —— Docker 下填错路径很常见，但校验本身也会失败。
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useState } from "react";

import MobileSavePathField from "@/components/mobile/MobileSavePathField";

const { mockApi } = vi.hoisted(() => ({
  mockApi: { listDirectories: vi.fn(), checkPath: vi.fn() },
}));
vi.mock("@/lib/api", () => ({ api: mockApi }));

const ROOT = String.raw`\\NAS\share`;
const LEVEL1 = String.raw`\\NAS\share\视频`;
const LEVEL2 = String.raw`\\NAS\share\视频\电视剧`;

/** 按 /fs/list 的真实契约构造：6 个字段，path 是服务端认定的当前目录 */
function fsList(path: string, parent: string, dirs: { name: string; path: string }[], error = "") {
  return { path, parent, separator: "\\", is_root_list: path === "", dirs, error };
}

function Harness({ initial = "" }: { initial?: string }) {
  const [path, setPath] = useState(initial);
  return (
    <div>
      <MobileSavePathField value={path} onChange={setPath} defaultPath={LEVEL1} />
      <output data-testid="current">{path}</output>
    </div>
  );
}

beforeEach(() => {
  Object.values(mockApi).forEach(fn => fn.mockReset());
  mockApi.checkPath.mockResolvedValue({
    path: LEVEL1, exists: true, is_dir: true, readable: true, hint: "",
  });
  mockApi.listDirectories.mockImplementation(async (path: string) => {
    if (!path) return fsList("", "", [{ name: "share", path: ROOT }]);
    if (path === ROOT) return fsList(ROOT, "", [{ name: "视频", path: LEVEL1 }]);
    if (path === LEVEL1) return fsList(LEVEL1, ROOT, [{ name: "电视剧", path: LEVEL2 }]);
    if (path === LEVEL2) return fsList(LEVEL2, LEVEL1, []);
    return fsList(path, "", [], "路径不存在");
  });
});

// 防抖是 600ms，waitFor 的等待窗口要盖过它
const DEBOUNCED = { timeout: 2000 };

/** 让 React 把在途的 effect 和微任务跑完 */
async function flush() {
  await act(async () => { await Promise.resolve(); });
}

describe("保存路径字段", () => {
  it("默认路径作为占位提示，不直接写进值里", async () => {
    render(<Harness />);
    expect(screen.getByLabelText("保存目录")).toHaveAttribute("placeholder", LEVEL1);
    expect(screen.getByTestId("current")).toHaveTextContent("");
  });

  it("手动输入后走 checkPath，可达时给出正面提示", async () => {
    render(<Harness />);
    fireEvent.change(screen.getByLabelText("保存目录"), { target: { value: LEVEL1 } });

    await flush();
    await waitFor(() => expect(screen.getByText("服务端可以访问这个目录")).toBeInTheDocument(), DEBOUNCED);
    expect(mockApi.checkPath).toHaveBeenCalledWith(LEVEL1);
  });

  it("路径不可达时显示后端 hint，但输入框仍保留用户填的值（不阻止提交）", async () => {
    mockApi.checkPath.mockResolvedValue({
      path: "/host/media", exists: false, is_dir: false, readable: false,
      hint: "容器里访问不到这个路径，请确认已挂载",
    });

    render(<Harness />);
    fireEvent.change(screen.getByLabelText("保存目录"), { target: { value: "/host/media" } });

    await flush();
    await waitFor(() => {
      expect(screen.getByText("容器里访问不到这个路径，请确认已挂载")).toBeInTheDocument();
    }, DEBOUNCED);
    // 值没有被清掉或改写
    expect(screen.getByTestId("current")).toHaveTextContent("/host/media");
  });

  it("校验请求本身失败时说清是校验失败，不说成路径有问题", async () => {
    mockApi.checkPath.mockRejectedValue(new Error("后端没起来"));

    render(<Harness />);
    fireEvent.change(screen.getByLabelText("保存目录"), { target: { value: "/x" } });

    await flush();
    await waitFor(() => expect(screen.getByText(/无法校验这个路径/)).toBeInTheDocument(), DEBOUNCED);
  });

  it("连续输入只在防抖结束后校验一次", async () => {
    render(<Harness />);
    const input = screen.getByLabelText("保存目录");
    fireEvent.change(input, { target: { value: "/a" } });
    fireEvent.change(input, { target: { value: "/ab" } });
    fireEvent.change(input, { target: { value: "/abc" } });

    await flush();
    await waitFor(() => expect(mockApi.checkPath).toHaveBeenCalledTimes(1), DEBOUNCED);
    expect(mockApi.checkPath).toHaveBeenCalledWith("/abc");
  });

  it("清空输入时不发校验请求", async () => {
    render(<Harness initial={LEVEL1} />);
    await flush();
    mockApi.checkPath.mockClear();

    fireEvent.change(screen.getByLabelText("保存目录"), { target: { value: "" } });
    await flush();

    expect(mockApi.checkPath).not.toHaveBeenCalled();
  });
});

describe("全屏目录选择 sheet", () => {
  /** 打开 sheet。它会从当前值（没有则从默认路径）所在目录开始，不是从根 */
  async function openSheet(initial?: string) {
    render(<Harness initial={initial} />);
    fireEvent.click(screen.getByRole("button", { name: "浏览" }));
    await flush();
    await waitFor(() => expect(screen.getByRole("dialog", { name: "选择保存目录" })).toBeInTheDocument());
  }

  it("打开时定位到默认路径所在目录，省掉从根一级级点下来", async () => {
    await openSheet();
    // defaultPath 是 …\视频，所以列出的是它的子目录
    await waitFor(() => expect(screen.getByRole("button", { name: /电视剧/ })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "用这里" })).toBeEnabled();
  });

  it("整行可点，逐级进入子目录", async () => {
    await openSheet();
    // 先回根，验证完整的逐级下钻
    fireEvent.click(screen.getByRole("button", { name: "根目录" }));
    await flush();
    await waitFor(() => expect(screen.getByRole("button", { name: /share/ })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /share/ }));
    await flush();
    await waitFor(() => expect(screen.getByRole("button", { name: /视频/ })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /视频/ }));
    await flush();
    await waitFor(() => expect(screen.getByRole("button", { name: /电视剧/ })).toBeInTheDocument());
  });

  it("能返回上一级", async () => {
    await openSheet();
    fireEvent.click(screen.getByRole("button", { name: /电视剧/ }));
    await flush();
    await waitFor(() => expect(screen.getByText("这个目录下没有子文件夹")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "上一级" }));
    await flush();
    // 回到 …\视频，重新看到「电视剧」这一项
    await waitFor(() => expect(screen.getByRole("button", { name: /电视剧/ })).toBeInTheDocument());
  });

  it("选中的目录回填到输入框并关闭 sheet", async () => {
    await openSheet();
    await waitFor(() => expect(screen.getByRole("button", { name: /电视剧/ })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /电视剧/ }));
    await flush();
    await waitFor(() => expect(screen.getByRole("button", { name: "用这里" })).toBeEnabled());

    fireEvent.click(screen.getByRole("button", { name: "用这里" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "选择保存目录" })).not.toBeInTheDocument();
    });
    expect(screen.getByTestId("current")).toHaveTextContent(LEVEL2);
  });

  it("根列表下没有当前目录，「用这里」不可点", async () => {
    await openSheet();
    fireEvent.click(screen.getByRole("button", { name: "根目录" }));
    await flush();
    await waitFor(() => expect(screen.getByRole("button", { name: /share/ })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "用这里" })).toBeDisabled();
  });

  it("目录为空时明确说明，不是空白", async () => {
    await openSheet();
    fireEvent.click(screen.getByRole("button", { name: /电视剧/ }));
    await flush();
    await waitFor(() => expect(screen.getByText("这个目录下没有子文件夹")).toBeInTheDocument());
  });

  it("后端返回 error 时用 alert 显示出来", async () => {
    mockApi.listDirectories.mockResolvedValue(fsList("", "", [], "没有权限读取这个目录"));
    await openSheet();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("没有权限读取这个目录"));
  });

  it("请求抛异常时也给出可读原因", async () => {
    mockApi.listDirectories.mockRejectedValue(new Error("网络不可达"));
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "浏览" }));
    await flush();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/网络不可达/));
  });

  it("取消不改变已有值", async () => {
    render(<Harness initial={LEVEL2} />);
    await flush();
    fireEvent.click(screen.getByRole("button", { name: "浏览" }));
    await flush();
    fireEvent.click(screen.getByRole("button", { name: "取消" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "选择保存目录" })).not.toBeInTheDocument();
    });
    expect(screen.getByTestId("current")).toHaveTextContent(LEVEL2);
  });
});
