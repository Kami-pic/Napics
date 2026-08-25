// 把 /m 的缩放手势锁掉。
//
// 为什么不能只靠 viewport meta：**iOS Safari 故意忽略 `user-scalable=no` 与
// `maximum-scale`**（出于无障碍考虑），双指还是能把整页放大，放大后页面可以左右拖，
// 底栏和页头会跟着跑出屏幕 —— 这是移动端最容易被识别成"网页壳"的地方。
//
// 为什么不用 CSS `touch-action: pan-y` 一把解决：`touch-action` 按祖先链**求交**，
// 在 /m 根节点上写 pan-y 会让子树里所有横向滚动容器都拖不动
// （搜索页的源状态行就是一个），代价比收益大。
//
// 双击判定必须带**坐标约束**：只比时间会把"300ms 内点两个不同元素"也判成双击，
// 而取消 touchend 会连带取消浏览器合成的 click —— 用户的第二次点击被静默吞掉，
// 命中面是整个 /m（列表快速下钻、字幕连续切轨、底栏切 Tab）。
"use client";
import { useEffect } from "react";

/** 两次触摸相距多少像素以内才算同一次双击 */
const DOUBLE_TAP_RADIUS_PX = 30;
const DOUBLE_TAP_INTERVAL_MS = 300;

export default function MobileGestureLock() {
  useEffect(() => {
    // Safari 专有事件（双指缩放），非 iOS 上不会触发，加了也无害
    const blockGesture = (e: Event) => e.preventDefault();

    let lastTap = { time: 0, x: 0, y: 0 };
    const blockDoubleTapZoom = (e: TouchEvent) => {
      const touch = e.changedTouches[0];
      const now = Date.now();
      const x = touch?.clientX ?? 0;
      const y = touch?.clientY ?? 0;

      // 播放器自己的控件在 shadow DOM 里，事件同样冒泡到 document。
      // 连点播放/暂停不该被当成双击缩放。
      const onMediaElement = e.target instanceof Element && e.target.closest("video, audio");

      const sameSpot =
        Math.abs(x - lastTap.x) < DOUBLE_TAP_RADIUS_PX &&
        Math.abs(y - lastTap.y) < DOUBLE_TAP_RADIUS_PX;
      if (!onMediaElement && now - lastTap.time < DOUBLE_TAP_INTERVAL_MS && sameSpot) {
        e.preventDefault();
      }
      lastTap = { time: now, x, y };
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
