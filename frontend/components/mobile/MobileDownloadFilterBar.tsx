// 下载任务筛选：全部 / 进行中 / 需处理 / 已完成。
//
// 互斥单选用 radiogroup 语义（和字幕轨切换一致），不是一排 aria-pressed 的开关。
// 计数直接标在 chip 上：任务多了以后，用户第一眼要知道有没有需要介入的。
"use client";
import {
  MOBILE_DOWNLOAD_FILTERS,
  type MobileDownloadFilterKey,
} from "@/lib/mobile/mobileDownloadFilters";

export interface MobileDownloadFilterBarProps {
  active: MobileDownloadFilterKey;
  counts: Record<MobileDownloadFilterKey, number>;
  onChange: (key: MobileDownloadFilterKey) => void;
}

export default function MobileDownloadFilterBar({ active, counts, onChange }: MobileDownloadFilterBarProps) {
  return (
    <div
      role="radiogroup"
      aria-label="任务筛选"
      className="-mx-[var(--m-page-px)] flex gap-2 overflow-x-auto px-[var(--m-page-px)]"
      style={{ scrollbarWidth: "none" }}
    >
      {MOBILE_DOWNLOAD_FILTERS.map(filter => {
        const checked = filter.key === active;
        const count = counts[filter.key];
        // 需处理为 0 时不强调，避免把一个空分类做成红点
        const emphasize = filter.key === "attention" && count > 0;
        return (
          <button
            key={filter.key}
            type="button"
            role="radio"
            aria-checked={checked}
            onClick={() => onChange(filter.key)}
            className="shrink-0 whitespace-nowrap rounded-[var(--m-radius-pill)] px-3 text-[13px]"
            style={{
              minHeight: "36px",
              background: checked ? "var(--m-accent-weak)" : "var(--m-surface)",
              border: `1px solid ${checked ? "var(--m-accent)" : "var(--m-border)"}`,
              color: emphasize && !checked ? "var(--m-warning)" : checked ? "var(--m-text)" : "var(--m-text-dim)",
            }}
          >
            {filter.label} {count}
          </button>
        );
      })}
    </div>
  );
}
