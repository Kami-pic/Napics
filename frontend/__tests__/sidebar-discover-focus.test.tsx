// 侧边栏的蓝色高亮同时只能给一个区：在发现区时目录不亮，在媒体库时发现不亮。
// 另外「发现」按钮的显示不该跟当前目录绑定 —— 用户在子文件夹里也要能去发现页。
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import Sidebar from "@/components/layout/Sidebar";
import type { FolderNode } from "@/types";

const CHILD: FolderNode = {
  name: "动画番", path: "\\\\niuniuos\\video\\动画番", video_count: 12,
  children: [], videos: [],
} as unknown as FolderNode;

const TREE: FolderNode = {
  name: "媒体库", path: "", video_count: 12, children: [CHILD], videos: [],
} as unknown as FolderNode;

function renderSidebar(over: Partial<React.ComponentProps<typeof Sidebar>> = {}) {
  return render(
    <Sidebar
      tree={TREE}
      currentFolder={CHILD}
      onNavigate={vi.fn()}
      collapsed={false}
      onToggle={vi.fn()}
      showDiscover
      onScrollToDiscover={vi.fn()}
      {...over}
    />,
  );
}

function rowOf(text: string): HTMLElement {
  const el = screen.getByText(text);
  return (el.closest("div,button") as HTMLElement) || el;
}

describe("侧边栏焦点", () => {
  it("焦点在媒体库时，选中目录是蓝的、发现不是", () => {
    renderSidebar({ activeSection: "library" });
    expect(rowOf("动画番").className).toContain("text-blue-400");
    expect(rowOf("发现").className).not.toContain("text-blue-400");
  });

  it("焦点在发现区时，发现是蓝的、目录让出高亮", () => {
    renderSidebar({ activeSection: "discover" });
    expect(rowOf("发现").className).toContain("text-blue-400");
    expect(rowOf("动画番").className).not.toContain("text-blue-400");
  });

  it("没传 activeSection 时按媒体库处理", () => {
    renderSidebar();
    expect(rowOf("动画番").className).toContain("text-blue-400");
  });

  it("在子文件夹里也能看到「发现」入口", () => {
    renderSidebar({ currentFolder: CHILD, activeSection: "library" });
    expect(screen.getByText("发现")).toBeTruthy();
  });

  it("点「发现」调用外部导航回调（由页面负责先回根目录）", () => {
    const onScrollToDiscover = vi.fn();
    renderSidebar({ onScrollToDiscover });
    (rowOf("发现") as HTMLButtonElement).click();
    expect(onScrollToDiscover).toHaveBeenCalledTimes(1);
  });
});
