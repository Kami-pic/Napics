// 资源搜索的 BT / 网盘 Tab：移动端一行等宽分段控件，全名 + 大热区。
"use client";
import type { MobileSearchTab } from "@/lib/mobile/mobileRouteUtils";

export interface MobileSearchTabsProps {
  tab: MobileSearchTab;
  onTabChange: (tab: MobileSearchTab) => void;
  btCount: number;
  panCount: number;
}

const TABS: { key: MobileSearchTab; label: string }[] = [
  { key: "bt", label: "BT / 磁力" },
  { key: "pan", label: "网盘" },
];

export default function MobileSearchTabs({ tab, onTabChange, btCount, panCount }: MobileSearchTabsProps) {
  const counts: Record<MobileSearchTab, number> = { bt: btCount, pan: panCount };

  return (
    <div
      role="tablist"
      aria-label="搜索来源"
      className="flex gap-1 rounded-[var(--m-radius)] p-1"
      style={{ background: "var(--m-surface)" }}
    >
      {TABS.map(item => {
        const active = tab === item.key;
        const count = counts[item.key];
        return (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onTabChange(item.key)}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-[var(--m-radius-sm)] text-sm font-medium"
            style={{
              minHeight: "var(--m-touch-min)",
              background: active ? "var(--m-accent-weak)" : "transparent",
              color: active ? "var(--m-accent)" : "var(--m-text-muted)",
            }}
          >
            {item.label}
            {count > 0 && (
              <span
                className="rounded-full px-1.5 text-xs"
                style={{
                  background: active ? "var(--m-accent)" : "var(--m-surface-raised)",
                  color: active ? "var(--m-on-accent)" : "var(--m-text-dim)",
                }}
              >
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
