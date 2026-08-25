// 把 /m 的手势锁成"只能上下滚"。
//
// 为什么不能只靠 viewport meta：**iOS Safari 故意忽略 `user-scalable=no` 与
// `maximum-scale`**（出于无障碍考虑），双指还是能把整页放大，放大后页面可以左右拖，
// 底栏和页头会跟着跑出屏幕 —— 这是移动端最容易被识别成"网页壳"的地方。
//
// 所以 iOS 上要拦 Safari 专有的 gesture 事件（双指缩放）和双击缩放。
// CSS 侧的 overscroll-behavior / touch-action 在 .m-app 里（见 globals.css）。
//
// 只挂在 /m 段，桌面页不受影响。
"use client";
import { useEffect } from "react";

export default function MobileGestureLock() {
  useEffect(() => {
    // Safari 专有事件，非 iOS 上不会触发，加了也无害
    const blockGesture = (e: Event) => e.preventDefault();
    // 双击缩放：两次 touchend 间隔小于 300ms 就拦掉第二次
    let lastTouchEnd = 0;
    const blockDoubleTapZoom = (e: TouchEvent) => {
      const now = Date.now();
      if (now - lastTouchEnd < 300) e.preventDefault();
      lastTouchEnd = now;
    };

    for (const type of ["gesturestart", "gesturechange", "gestureend"]) {
      document.addEventListener(type, blockGesture, { passive: false });
    }
    document.addEventListener("touchend", blockDoubleTapZoom, { passive: false });

    return () => {
      for (const type of ["gesturestart", "gesturechange", "gestureend"]) {
        document.removeEventListener(type, blockGesture);
      }
      document.removeEventListener("touchend", blockDoubleTapZoom);
    };
  }, []);

  return null;
}
