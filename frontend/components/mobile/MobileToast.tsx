// 瞬时反馈（复制成功 / 失败、提交结果）。
// 复制失败必须说清楚，不能静默 —— 用户会以为复制成功了然后去粘贴一片空白。
"use client";
import { useEffect } from "react";

export interface MobileToastProps {
  message: string;
  ok: boolean;
  onDismiss: () => void;
  /** 自动消失时间；传 0 表示不自动消失 */
  duration?: number;
}

export default function MobileToast({ message, ok, onDismiss, duration = 3000 }: MobileToastProps) {
  useEffect(() => {
    if (!message || duration <= 0) return;
    const timer = setTimeout(onDismiss, duration);
    return () => clearTimeout(timer);
  }, [message, duration, onDismiss]);

  if (!message) return null;

  return (
    <div
      className="fixed left-0 right-0 z-50 flex justify-center"
      style={{ bottom: "calc(var(--m-nav-h) + var(--m-safe-bottom) + 16px)" }}
      role="status"
      aria-live="polite"
    >
      <div
        className="max-w-[90vw] break-words rounded-full px-4 py-2 text-xs"
        style={{
          background: "var(--m-surface-raised)",
          color: ok ? "var(--m-success)" : "var(--m-danger)",
        }}
      >
        {message}
      </div>
    </div>
  );
}
