// 功能发现轻提示 — 首次使用时短暂显示，不打断操作
"use client";
import { useState, useEffect } from "react";

interface FeatureTipProps {
  /** localStorage key，用于记录是否已展示过 */
  tipKey: string;
  /** 提示文案 */
  message: string;
  /** 自动消失时间（ms），默认 4000 */
  duration?: number;
}

export default function FeatureTip({ tipKey, message, duration = 4000 }: FeatureTipProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const storageKey = `napics_tip_${tipKey}`;
    if (localStorage.getItem(storageKey)) return;
    // 延迟 500ms 再显示，避免页面刚加载就弹
    const showTimer = setTimeout(() => setVisible(true), 500);
    const hideTimer = setTimeout(() => {
      setVisible(false);
      localStorage.setItem(storageKey, "1");
    }, 500 + duration);
    return () => { clearTimeout(showTimer); clearTimeout(hideTimer); };
  }, [tipKey, duration]);

  if (!visible) return null;

  return (
    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 z-20 animate-fade-in">
      <div className="px-3 py-1.5 rounded-lg bg-blue-600/90 text-[11px] text-white whitespace-nowrap shadow-lg backdrop-blur-sm">
        {message}
      </div>
    </div>
  );
}
