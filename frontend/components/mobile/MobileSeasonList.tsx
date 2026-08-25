// 季列表。顺序由 libraryNav 的季号解析决定，这里不再排序。
"use client";
import type { FolderNode } from "@/types";
import { nodeDisplayName, seasonNumber } from "@/lib/mobile/libraryNav";

export interface MobileSeasonListProps {
  seasons: FolderNode[];
  onOpen: (season: FolderNode) => void;
}

export default function MobileSeasonList({ seasons, onOpen }: MobileSeasonListProps) {
  return (
    <ul className="flex flex-col gap-2" aria-label="季列表">
      {seasons.map(season => {
        const num = seasonNumber(season.name) ?? seasonNumber(nodeDisplayName(season));
        return (
          <li key={season.path}>
            <button
              type="button"
              onClick={() => onOpen(season)}
              className="flex w-full items-center gap-3 rounded-[var(--m-radius)] px-3 text-left active:bg-[var(--m-surface-raised)]"
              style={{
                minHeight: "var(--m-touch-min)",
                background: "var(--m-surface)",
                border: "1px solid var(--m-border)",
              }}
            >
              <span
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[13px] text-[var(--m-text-muted)]"
                style={{ background: "var(--m-surface-raised)" }}
                aria-hidden="true"
              >
                {num === null ? "SP" : `S${String(num).padStart(2, "0")}`}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] text-[var(--m-text)]">{nodeDisplayName(season)}</span>
                <span className="text-[12px] text-[var(--m-text-dim)]">{season.video_count} 集</span>
              </span>
              <svg
                className="h-4 w-4 shrink-0 text-[var(--m-text-dim)]"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path d="m9 18 6-6-6-6" />
              </svg>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
