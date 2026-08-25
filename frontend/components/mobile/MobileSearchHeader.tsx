// 移动端搜索头：输入框 + BT/网盘 Tab。桌面那套密集工具栏不搬过来。
"use client";
import type { MobileSearchTab } from "@/lib/mobile/mobileRouteUtils";

export interface MobileSearchHeaderProps {
  draft: string;
  onDraftChange: (value: string) => void;
  onSubmit: () => void;
  tab: MobileSearchTab;
  onTabChange: (tab: MobileSearchTab) => void;
  btCount: number;
  panCount: number;
}

const TABS: { key: MobileSearchTab; label: string }[] = [
  { key: "bt", label: "BT / 磁力" },
  { key: "pan", label: "网盘" },
];

export default function MobileSearchHeader({
  draft, onDraftChange, onSubmit, tab, onTabChange, btCount, panCount,
}: MobileSearchHeaderProps) {
  const counts: Record<MobileSearchTab, number> = { bt: btCount, pan: panCount };

  return (
    <div className="flex flex-col gap-3 pt-3">
      <form
        onSubmit={e => { e.preventDefault(); onSubmit(); }}
        className="flex items-stretch gap-2"
      >
        <input
          value={draft}
          onChange={e => onDraftChange(e.target.value)}
          placeholder="片名、剧名或关键词"
          aria-label="搜索词"
          // search 类型让 iOS 键盘显示"搜索"键
          type="search"
          enterKeyHint="search"
          className="min-w-0 flex-1 rounded-[var(--m-radius)] border px-3 text-sm outline-none"
          style={{
            minHeight: "var(--m-touch-min)",
            background: "var(--m-surface)",
            borderColor: "var(--m-border)",
            color: "var(--m-text)",
          }}
        />
        <button
          type="submit"
          disabled={!draft.trim()}
          className="flex-shrink-0 rounded-[var(--m-radius)] px-4 text-sm font-medium disabled:opacity-40"
          style={{
            minHeight: "var(--m-touch-min)",
            background: "var(--m-accent)",
            color: "var(--m-on-accent)",
          }}
        >
          搜索
        </button>
      </form>

      <div role="tablist" aria-label="搜索来源" className="flex gap-2">
        {TABS.map(item => {
          const active = tab === item.key;
          return (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onTabChange(item.key)}
              className="flex items-center gap-1.5 rounded-full px-4 text-xs"
              style={{
                minHeight: "var(--m-touch-min)",
                background: active ? "var(--m-accent-weak)" : "var(--m-surface)",
                color: active ? "var(--m-accent)" : "var(--m-text-muted)",
              }}
            >
              {item.label}
              {counts[item.key] > 0 && <span>{counts[item.key]}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
