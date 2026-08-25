// 目录卡片列表（媒体库分级浏览的通用一层）。
// 单列行式而不是海报网格：媒体库这一层要看清完整的中文长名和视频数，
// 两列会把名字截成两三个字。海报网格留给发现页。
"use client";
import type { FolderNode } from "@/types";
import { nodeDisplayName } from "@/lib/mobile/libraryNav";

/** folder_type → 徽标文案。空串和未知类型不显示徽标，不编造类型 */
const TYPE_LABELS: Record<string, string> = {
  movie: "电影",
  tv: "剧集",
  season: "季",
  collection: "合集",
  series: "系列",
  mixed: "混合",
};

export interface MobileFolderListProps {
  folders: FolderNode[];
  onOpen: (node: FolderNode) => void;
  /** 无障碍用：这一组是什么 */
  ariaLabel?: string;
}

export default function MobileFolderList({ folders, onOpen, ariaLabel = "目录列表" }: MobileFolderListProps) {
  return (
    <ul className="flex flex-col gap-2" aria-label={ariaLabel}>
      {folders.map(node => {
        const label = TYPE_LABELS[node.folder_type || ""] || "";
        return (
          <li key={node.path}>
            <button
              type="button"
              onClick={() => onOpen(node)}
              className="flex w-full items-center gap-3 rounded-[var(--m-radius)] px-3 py-[var(--m-row-py)] text-left active:bg-[var(--m-surface-raised)]"
              style={{
                minHeight: "var(--m-touch-min)",
                background: "var(--m-surface)",
                border: "1px solid var(--m-border)",
              }}
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] text-[var(--m-text)]">{nodeDisplayName(node)}</span>
                <span className="mt-0.5 flex items-center gap-2 text-[12px] text-[var(--m-text-dim)]">
                  {label && (
                    <span
                      className="rounded-[var(--m-radius-sm)] px-1.5 py-px text-[11px] text-[var(--m-text-muted)]"
                      style={{ background: "var(--m-surface-raised)" }}
                    >
                      {label}
                    </span>
                  )}
                  <span>{node.video_count} 个视频</span>
                </span>
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
