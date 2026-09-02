// 焦点归属的判据：发现区**吸附到容器顶部**才算焦点在发现。
// 首页停在媒体库根目录时发现区就在下方露头，那时候高亮必须还在媒体库。
import { act, renderHook } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { useActiveSection } from "@/hooks/useActiveSection";

function elWithTop(top: number) {
  const el = document.createElement("div");
  el.getBoundingClientRect = () => ({ top } as DOMRect);
  return el;
}

function setTop(el: HTMLElement, top: number) {
  el.getBoundingClientRect = () => ({ top } as DOMRect);
}

function setup(wallTop: number, enabled = true) {
  const container = elWithTop(0);
  const wall = elWithTop(wallTop);
  const hook = renderHook(() => useActiveSection({
    containerRef: { current: container },
    wallRef: { current: wall },
    enabled,
  }));
  const scroll = () => act(() => { container.dispatchEvent(new Event("scroll")); });
  return { container, wall, hook, scroll };
}

describe("useActiveSection", () => {
  it("发现区在下方露头时，焦点仍在媒体库", () => {
    const { hook } = setup(400);
    expect(hook.result.current).toBe("library");
  });

  it("发现区吸附到顶部后焦点归发现", () => {
    const { wall, hook, scroll } = setup(400);
    setTop(wall, 0);
    scroll();
    expect(hook.result.current).toBe("discover");
  });

  it("滚回媒体库后焦点回来", () => {
    const { wall, hook, scroll } = setup(0);
    expect(hook.result.current).toBe("discover");
    setTop(wall, 620);
    scroll();
    expect(hook.result.current).toBe("library");
  });

  it("吸附动画收尾差几像素也算已吸附", () => {
    const { hook } = setup(12);
    expect(hook.result.current).toBe("discover");
  });

  it("刚露出一大半还不算（不是 IntersectionObserver 那套）", () => {
    const { hook } = setup(120);
    expect(hook.result.current).toBe("library");
  });

  it("没有发现区时恒为媒体库", () => {
    const { hook } = setup(0, false);
    expect(hook.result.current).toBe("library");
  });
});
