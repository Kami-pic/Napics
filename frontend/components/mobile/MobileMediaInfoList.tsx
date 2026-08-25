// 视频基本信息表。字段可能缺失（ffprobe 失败或旧条目），缺的行不渲染，
// 不显示"未知"占位堆满半屏。
"use client";
import type { VideoInfo } from "@/types";
import { formatSize, formatDuration } from "@/lib/utils";

export interface MobileMediaInfoListProps {
  video: VideoInfo;
}

export default function MobileMediaInfoList({ video }: MobileMediaInfoListProps) {
  // codec / duration_min 是新字段名，video_codec / duration 是旧版写过的遗留写法，
  // 两套都兜一下，否则存量条目这两行永远空着
  const codec = video.codec || video.video_codec || "";
  const duration = video.duration_min ?? video.duration;
  const subtitleText = video.subtitle_text_count;
  const subtitleGraphic = video.subtitle_graphic_count;

  const rows: [string, string][] = [
    ["文件名", video.file_name],
    ["分辨率", video.resolution],
    ["大小", formatSize(video.size_gb)],
    ["时长", duration ? formatDuration(duration) : ""],
    ["视频编码", codec],
    ["音频编码", video.audio_codec],
    ["HDR", video.hdr_type],
    [
      "内封字幕",
      video.subtitle_count > 0
        ? subtitleText === undefined && subtitleGraphic === undefined
          ? `${video.subtitle_count} 条`
          : `${video.subtitle_count} 条（文本 ${subtitleText ?? 0} / 图形 ${subtitleGraphic ?? 0}）`
        : "",
    ],
    ["路径", video.file_path],
  ];

  return (
    <dl
      className="flex flex-col gap-2 rounded-[var(--m-radius)] p-3"
      style={{ background: "var(--m-surface)", border: "1px solid var(--m-border)" }}
    >
      {rows
        .filter(([, value]) => value && value !== "—")
        .map(([label, value]) => (
          <div key={label} className="flex gap-3 text-[13px]">
            <dt className="w-16 shrink-0 text-[var(--m-text-dim)]">{label}</dt>
            <dd className="min-w-0 flex-1 break-all text-[var(--m-text-muted)]">{value}</dd>
          </div>
        ))}
    </dl>
  );
}
