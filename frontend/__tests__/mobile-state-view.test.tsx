// 锁定四态各自渲染对应内容，且不互相串。
//
// 这个组件是移动端 Loading / Empty / Error 的唯一出口 —— 它一旦静默返回空，
// 表现就是白屏，而白屏在真机上完全无法判断是加载中还是出错了。
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import MobileStateView from "@/components/mobile/MobileStateView";

describe("MobileStateView", () => {
  it("loading 态显示加载文案", () => {
    render(<MobileStateView state="loading">内容</MobileStateView>);
    expect(screen.getByText("加载中…")).toBeInTheDocument();
    expect(screen.queryByText("内容")).not.toBeInTheDocument();
  });

  it("empty 态显示空状态文案，不显示错误", () => {
    render(<MobileStateView state="empty">内容</MobileStateView>);
    expect(screen.getByText("这里还没有内容")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("error 态用 alert 角色显示错误文案", () => {
    render(<MobileStateView state="error" errorText="媒体库加载失败">内容</MobileStateView>);
    expect(screen.getByRole("alert")).toHaveTextContent("媒体库加载失败");
    expect(screen.queryByText("内容")).not.toBeInTheDocument();
  });

  it("ready 态渲染子内容，不再显示任何状态文案", () => {
    render(<MobileStateView state="ready">内容</MobileStateView>);
    expect(screen.getByText("内容")).toBeInTheDocument();
    expect(screen.queryByText("加载中…")).not.toBeInTheDocument();
    expect(screen.queryByText("这里还没有内容")).not.toBeInTheDocument();
  });

  it("自定义文案覆盖默认值", () => {
    render(<MobileStateView state="empty" emptyText="这个目录下没有视频" />);
    expect(screen.getByText("这个目录下没有视频")).toBeInTheDocument();
  });

  it("error 态给了 onRetry 才有重试按钮，点击会触发", () => {
    const onRetry = vi.fn();
    const { unmount } = render(<MobileStateView state="error" onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(onRetry).toHaveBeenCalledOnce();
    unmount();

    render(<MobileStateView state="error" />);
    expect(screen.queryByRole("button", { name: "重试" })).not.toBeInTheDocument();
  });

  it("empty 态可以挂引导操作", () => {
    render(<MobileStateView state="empty" emptyAction={<button type="button">去搜索</button>} />);
    expect(screen.getByRole("button", { name: "去搜索" })).toBeInTheDocument();
  });
});
