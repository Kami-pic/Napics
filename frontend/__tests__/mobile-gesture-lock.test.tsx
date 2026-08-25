// /m 的缩放手势锁定。
//
// 两件事同等重要：拦住缩放，**以及不吞正常点击**。
// 取消 touchend 会连带取消浏览器合成的 click，所以双击判定只比时间不比坐标时，
// "300ms 内点两个不同元素"的第二次点击会被静默丢掉。
import { act, render } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import MobileGestureLock from "@/components/mobile/MobileGestureLock";

/** 派发带坐标的 touchend，返回是否被 preventDefault */
function tap(x: number, y: number, target?: Element): boolean {
  const event = new Event("touchend", { cancelable: true, bubbles: true }) as Event & {
    changedTouches: { clientX: number; clientY: number }[];
  };
  Object.defineProperty(event, "changedTouches", {
    value: [{ clientX: x, clientY: y }],
  });
  (target ?? document.body).dispatchEvent(event);
  return event.defaultPrevented;
}

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
  document.body.innerHTML = "";
});

describe("拦住缩放", () => {
  it("Safari 的双指缩放三个事件都被拦", () => {
    render(<MobileGestureLock />);
    for (const type of ["gesturestart", "gesturechange", "gestureend"]) {
      expect(fire(type)).toBe(true);
    }
  });

  it("同一位置 300ms 内连点两次 = 双击缩放，拦掉第二次", () => {
    render(<MobileGestureLock />);
    expect(tap(100, 200)).toBe(false);
    act(() => { vi.advanceTimersByTime(120); });
    expect(tap(105, 203)).toBe(true);
  });
});

describe("不吞正常点击", () => {
  it("300ms 内点两个相距较远的位置不算双击（列表快速下钻、连续切字幕轨）", () => {
    render(<MobileGestureLock />);
    expect(tap(50, 100)).toBe(false);
    act(() => { vi.advanceTimersByTime(80); });
    expect(tap(50, 400)).toBe(false);      // 同一列但差 300px
    act(() => { vi.advanceTimersByTime(80); });
    expect(tap(300, 400)).toBe(false);     // 横向差 250px
  });

  it("同一位置但间隔超过 300ms 不算双击", () => {
    render(<MobileGestureLock />);
    expect(tap(100, 200)).toBe(false);
    act(() => { vi.advanceTimersByTime(400); });
    expect(tap(100, 200)).toBe(false);
  });

  it("落在 video 上的连点不拦：原生控件的播放/暂停要能连按", () => {
    const video = document.createElement("video");
    document.body.appendChild(video);
    render(<MobileGestureLock />);
    expect(tap(10, 10, video)).toBe(false);
    act(() => { vi.advanceTimersByTime(100); });
    expect(tap(10, 10, video)).toBe(false);
  });
});

describe("清理", () => {
  it("卸载后不再拦截，不给桌面页留下全局监听", () => {
    const { unmount } = render(<MobileGestureLock />);
    expect(fire("gesturestart")).toBe(true);
    unmount();
    expect(fire("gesturestart")).toBe(false);
    expect(tap(100, 200)).toBe(false);
    act(() => { vi.advanceTimersByTime(50); });
    expect(tap(100, 200)).toBe(false);
  });

  it("自身不渲染任何 DOM", () => {
    const { container } = render(<MobileGestureLock />);
    expect(container.innerHTML).toBe("");
  });
});
