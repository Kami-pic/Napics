// 移动端资源搜索头：只有输入框 + 搜索按钮。
// BT/网盘 Tab 挪到了页头 titlebar（见 MobileSearchClient 的 headerRight）；
// 搜索历史是片名搜索的事，这页不放（见 MobileDiscoverSearchClient / DiscoverHeader）。
"use client";

export interface MobileSearchHeaderProps {
  draft: string;
  onDraftChange: (value: string) => void;
  onSubmit: () => void;
}

export default function MobileSearchHeader({
  draft, onDraftChange, onSubmit,
}: MobileSearchHeaderProps) {
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
    </div>
  );
}
