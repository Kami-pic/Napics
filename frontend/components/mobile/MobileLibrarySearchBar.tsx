// 媒体库顶部的库内检索框。
//
// 和底栏「搜索」（豆瓣找片子）不是一件事：这里搜的是**已经入库的东西**，
// 纯前端在内存里的整树上过滤，不打后端。所以输入即出结果，不需要提交。
"use client";
import type { ChangeEvent } from "react";

export interface MobileLibrarySearchBarProps {
  value: string;
  onChange: (value: string) => void;
  /** 有词时显示命中数；截断了就说明还有更多 */
  hint?: string;
}

export default function MobileLibrarySearchBar({ value, onChange, hint }: MobileLibrarySearchBarProps) {
  return (
    <div className="flex flex-col gap-1 pt-3">
      <div className="relative flex items-center">
        <svg
          className="pointer-events-none absolute left-3 h-4 w-4 text-[var(--m-text-dim)]"
          fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true"
        >
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
        </svg>
        <input
          type="search"
          value={value}
          onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
          placeholder="在媒体库里找…"
          aria-label="媒体库检索"
          className="w-full rounded-[var(--m-radius)] pl-9 pr-3 text-[15px] text-[var(--m-text)] outline-none"
          style={{
            minHeight: "var(--m-touch-min)",
            background: "var(--m-surface)",
            border: "1px solid var(--m-border)",
          }}
        />
      </div>
      {hint && <p className="px-1 text-[11px] text-[var(--m-text-dim)]">{hint}</p>}
    </div>
  );
}
