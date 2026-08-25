// 集 / 视频列表。点条目进详情（不直接播放，见 TODO §六 矩阵），
// 行尾的播放按钮才是直达 /m/play 的入口。
"use client";
import type { VideoInfo } from "@/types";
import { videoDisplayName } from "@/lib/mobile/libraryNav";
import { formatSize } from "@/lib/utils";

export interface MobileEpisodeListProps {
  videos: VideoInfo[];
  onOpenDetail: (video: VideoInfo) => void;
  onPlay: (video: VideoInfo) => void;
}

export default function MobileEpisodeList({ videos, onOpenDetail, onPlay }: MobileEpisodeListProps) {
  return (
    <ul className="flex flex-col gap-2" aria-label="视频列表">
      {videos.map((video, idx) => (
        <li key={video.file_path}>
          <div
            className="flex items-center gap-2 rounded-[var(--m-radius)] pr-1"
            style={{ background: "var(--m-surface)", border: "1px solid var(--m-border)" }}
          >
            <button
              type="button"
              onClick={() => onOpenDetail(video)}
              className="flex min-w-0 flex-1 items-center gap-3 px-3 text-left active:bg-[var(--m-surface-raised)]"
              style={{ minHeight: "var(--m-touch-min)", paddingTop: 10, paddingBottom: 10 }}
            >
              <span className="w-6 shrink-0 text-[12px] tabular-nums text-[var(--m-text-dim)]" aria-hidden="true">
                {String(idx + 1).padStart(2, "0")}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] text-[var(--m-text)]">{videoDisplayName(video)}</span>
                <span className="flex items-center gap-2 text-[12px] text-[var(--m-text-dim)]">
                  {video.resolution && <span>{video.resolution}</span>}
                  <span>{formatSize(video.size_gb)}</span>
                  {video.hdr_type && <span>{video.hdr_type}</span>}
                </span>
              </span>
            </button>
            <button
              type="button"
              onClick={() => onPlay(video)}
              aria-label={`播放 ${videoDisplayName(video)}`}
              className="flex shrink-0 items-center justify-center rounded-lg text-[var(--m-text-muted)] active:bg-[var(--m-surface-raised)]"
              style={{ minHeight: "var(--m-touch-min)", minWidth: "var(--m-touch-min)" }}
            >
              <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M8 5v14l11-7z" />
              </svg>
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
