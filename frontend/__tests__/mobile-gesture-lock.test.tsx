// /m 的手势锁定：双指缩放与双击缩放要被拦掉。
//
// 为什么需要 JS 而不是只写 viewport meta：**iOS Safari 故意忽略
// `user-scalable=no` 和 `maximum-scale`**，光靠 meta 双指还是能把整页放大，
// 放大后页面能左右拖，页头和底栏会跑出屏幕。
import { act, render } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import MobileGestureLock from "@/components/mobile/MobileGestureLock";

/** 派发一个可取消的事件，返回是否被 preventDefault */
function fire(type: string): boolean {
  const event = new Event(type, { cancelable: true, bubbles: true });
  document.dispatchEvent(event);
  return event.defaultPrevented;
}

beforeEach(() => {
  // fake timer 必须在 render 之前装
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("手势锁定", () => {
  it("拦掉 Safari 的双指缩放三个事件", () => {
    render(<MobileGestureLock />);
    for (const type of ["gesturestart", "gesturechange", "gestureend"]) {
      expect(fire(type)).toBe(true);
    }
  });

  it("间隔小于 300ms 的第二次 touchend 被拦（双击缩放）", () => {
    render(<MobileGestureLock />);
    expect(fire("touchend")).toBe(false);       // 第一次是正常点击
    act(() => { vi.advanceTimersByTime(100); });
    expect(fire("touchend")).toBe(true);        // 300ms 内的第二次 = 双击
  });

  it("间隔超过 300ms 的连续点击不受影响", () => {
    render(<MobileGestureLock />);
    expect(fire("touchend")).toBe(false);
    act(() => { vi.advanceTimersByTime(400); });
    expect(fire("touchend")).toBe(false);
  });

  it("卸载后不再拦截，不给桌面页留下全局监听", () => {
    const { unmount } = render(<MobileGestureLock />);
    expect(fire("gesturestart")).toBe(true);
    unmount();
    expect(fire("gesturestart")).toBe(false);
    expect(fire("touchend")).toBe(false);
  });

  it("自身不渲染任何 DOM", () => {
    const { container } = render(<MobileGestureLock />);
    expect(container.innerHTML).toBe("");
  });
});
