// 搜索源状态：哪些源在搜、哪些出了结果、哪些失败。
//
// 横向滚动、**纯展示不可点**，所以每项 32px 而不是 44px 的触控下限。
// 将来要给它加点击行为（比如点某源筛结果），高度必须先提到 var(--m-touch-min)。
"use client";

export type MobileSourceState = "idle" | "searching" | "done" | "failed" | "disabled";

export interface MobileSourceStatusItem {
  name: string;
  state: MobileSourceState;
  count: number;
}

const STATE_COLOR: Record<MobileSourceState, string> = {
  idle: "var(--m-text-dim)",
  searching: "var(--m-accent)",
  done: "var(--m-success)",
  failed: "var(--m-danger)",
  disabled: "var(--m-text-dim)",
};

export interface MobileSourceStatusRowProps {
  items: MobileSourceStatusItem[];
}

export default function MobileSourceStatusRow({ items }: MobileSourceStatusRowProps) {
  if (items.length === 0) return null;

  return (
    <ul className="flex gap-2 overflow-x-auto pb-1" aria-label="搜索源状态">
      {items.map(item => (
        <li
          key={item.name}
          className="flex flex-shrink-0 items-center gap-1.5 rounded-full px-3 text-[11px]"
          style={{ minHeight: "32px", background: "var(--m-surface)" }}
        >
          <span
            className="h-1.5 w-1.5 flex-shrink-0 rounded-full"
            style={{ background: STATE_COLOR[item.state] }}
            aria-hidden="true"
          />
          <span className="text-[var(--m-text-muted)]">{item.name}</span>
          {item.state === "done" && <span className="text-[var(--m-text-dim)]">{item.count}</span>}
          {item.state === "failed" && <span style={{ color: "var(--m-danger)" }}>失败</span>}
        </li>
      ))}
    </ul>
  );
}
