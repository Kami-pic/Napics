// 移动端搜索头：输入框 + BT/网盘 Tab + 搜索历史。桌面那套密集工具栏不搬过来。
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
  /** 搜索历史（最近在前）。空数组时不渲染这一行 */
  history: string[];
  /** 点历史词：直接用它重搜 */
  onPickHistory: (keyword: string) => void;
  /** 删单条历史词 */
  onRemoveHistory: (keyword: string) => void;
}

const TABS: { key: MobileSearchTab; label: string }[] = [
  { key: "bt", label: "BT / 磁力" },
  { key: "pan", label: "网盘" },
];

export default function MobileSearchHeader({
  draft, onDraftChange, onSubmit, tab, onTabChange, btCount, panCount,
  history, onPickHistory, onRemoveHistory,
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

      {/* 搜索历史：点整块用该词重搜，点 × 删这一条。最多 10 条，最近在前。 */}
      {history.length > 0 && (
        <div
          className="-mx-[var(--m-page-px)] flex items-center gap-2 overflow-x-auto px-[var(--m-page-px)]"
          style={{ scrollbarWidth: "none" }}
          aria-label="搜索历史"
        >
          <span className="shrink-0 text-[10px] text-[var(--m-text-dim)]">历史</span>
          {history.map(keyword => (
            <span
              key={keyword}
              className="flex shrink-0 items-center rounded-[var(--m-radius-pill)] text-xs"
              style={{ background: "var(--m-surface)", border: "1px solid var(--m-border)" }}
            >
              <button
                type="button"
                onClick={() => onPickHistory(keyword)}
                className="max-w-[8rem] truncate py-1 pl-2.5 pr-1 text-[var(--m-text)]"
                title={keyword}
              >
                {keyword}
              </button>
              <button
                type="button"
                onClick={() => onRemoveHistory(keyword)}
                aria-label={`删除历史词 ${keyword}`}
                className="px-1.5 py-1 text-[var(--m-text-dim)]"
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
