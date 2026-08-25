// 集 / 视频列表。点条目进详情（不直接播放，见 TODO §六 矩阵），
// 行尾的播放按钮才是直达 /m/play 的入口。
//
// 播放键静止态就带底色和分隔线：前几屏的行尾是纯装饰的 chevron，
// 用户会被训练成"行尾图标随便点"，这里同一位置的语义是"直接开播"。
// 靠 44×44 的热区大小不够，边界必须看得见。
"use client";
import type { VideoInfo } from "@/types";
import { videoDisplayName } from "@/lib/mobile/libraryNav";
import { formatSize } from "@/lib/utils";

export interface MobileEpisodeListProps {
  videos: VideoInfo[];
  onOpenDetail: (video: VideoInfo) => void;
  onPlay: (video: VideoInfo) => void;
  /** 分段标题，如"其他视频"。剧目录下的剧场版/SP 与季内集分开列 */
  title?: string;
  /** 序号从几开始显示；传 false 时不显示序号（非正片那一段） */
  numbered?: boolean;
}

export default function MobileEpisodeList({
  videos,
  onOpenDetail,
  onPlay,
  title,
  numbered = true,
}: MobileEpisodeListProps) {
  return (
    <section className="flex flex-col gap-2">
      {title && (
        <h2 className="px-1 text-[12px] text-[var(--m-text-dim)]">{title}</h2>
      )}
      <ul className="flex flex-col gap-2" aria-label={title || "视频列表"}>
        {videos.map((video, idx) => {
          const name = videoDisplayName(video);
          return (
            <li key={video.file_path}>
              <div
                className="flex items-stretch rounded-[var(--m-radius)]"
                style={{ background: "var(--m-surface)", border: "1px solid var(--m-border)" }}
              >
                <button
                  type="button"
                  onClick={() => onOpenDetail(video)}
                  aria-label={numbered ? `${idx + 1}. ${name}` : name}
                  className="flex min-w-0 flex-1 items-center gap-3 rounded-l-[var(--m-radius)] px-3 py-[var(--m-row-py)] text-left active:bg-[var(--m-surface-raised)]"
                  style={{ minHeight: "var(--m-touch-min)" }}
                >
                  {numbered && (
                    <span className="w-6 shrink-0 text-[12px] tabular-nums text-[var(--m-text-dim)]" aria-hidden="true">
                      {String(idx + 1).padStart(2, "0")}
                    </span>
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[15px] text-[var(--m-text)]">{name}</span>
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
                  aria-label={`播放 ${name}`}
                  className="my-2 mr-2 ml-1 flex shrink-0 items-center justify-center rounded-[var(--m-radius-pill)] text-[var(--m-text-muted)] active:bg-[var(--m-accent-weak)] active:text-[var(--m-accent)]"
                  style={{
                    minWidth: "var(--m-touch-min)",
                    background: "var(--m-surface-raised)",
                    border: "1px solid var(--m-border)",
                  }}
                >
                  <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
