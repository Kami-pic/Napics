// 榜单切换：横向滚动的胶囊 Tab。
//
// 用 tablist/tab 语义而不是一排普通按钮：这是互斥单选，读屏得能说出"8 之 3"。
// 横向滚动容器不能加 touch-action 限制（会连带锁死整棵子树的拖动，Phase 2 踩过）。
"use client";
import { useEffect, useRef } from "react";

import type { RecommendSource } from "@/components/media/discoverUtils";

export interface MobileDiscoverTabsProps {
  tabs: RecommendSource[];
  activeTab: string;
  onChange: (tab: string) => void;
}

export default function MobileDiscoverTabs({ tabs, activeTab, onChange }: MobileDiscoverTabsProps) {
  const activeRef = useRef<HTMLButtonElement>(null);

  // 从详情返回时选中项可能在屏幕外，滚进可视区，否则用户以为 tab 被重置了
  useEffect(() => {
    // jsdom 没有 scrollIntoView，可选调用避免测试环境炸掉
    activeRef.current?.scrollIntoView?.({ block: "nearest", inline: "center" });
  }, [activeTab]);

  return (
    <div
      role="tablist"
      aria-label="榜单"
      className="-mx-[var(--m-page-px)] flex gap-2 overflow-x-auto px-[var(--m-page-px)] py-2"
      style={{ scrollbarWidth: "none" }}
    >
      {tabs.map(tab => {
        const active = tab.key === activeTab;
        return (
          <button
            key={tab.key}
            ref={active ? activeRef : undefined}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.key)}
            className="shrink-0 whitespace-nowrap rounded-[var(--m-radius-pill)] px-3 text-[13px]"
            style={{
              minHeight: "36px",
              background: active ? "var(--m-accent-weak)" : "var(--m-surface)",
              border: `1px solid ${active ? "var(--m-accent)" : "var(--m-border)"}`,
              color: active ? "var(--m-text)" : "var(--m-text-dim)",
            }}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
