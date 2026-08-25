// 单个下载任务卡片：状态、进度、归位与入库结果
"use client";
import type { DownloadTone } from "@/lib/domain/download";
import type { LibraryConfirmState, MobileDownloadEntry } from "@/hooks/mobile/useMobileDownloads";

/** 语义 tone → 本页配色。共享模块只给 tone，配色由视图层决定 */
const TONE_VAR: Record<DownloadTone, string> = {
  pending: "var(--m-text-muted)",
  active: "var(--m-accent)",
  success: "var(--m-success)",
  warning: "var(--m-warning)",
  danger: "var(--m-danger)",
  muted: "var(--m-text-dim)",
};

const LIBRARY_TEXT: Record<LibraryConfirmState, string> = {
  not_applicable: "",
  // completed 只代表下载器侧完成，这里必须说清楚还在等入库，不能直接写"已入库"
  confirming: "正在确认是否进入媒体库…",
  confirmed: "已进入媒体库",
  timeout: "等待入库超时，可用下方「快速同步」恢复",
};

export interface MobileDownloadTaskCardProps {
  entry: MobileDownloadEntry;
}

export default function MobileDownloadTaskCard({ entry }: MobileDownloadTaskCardProps) {
  const { task, status, relocate, library } = entry;
  const percent = Math.round((task.progress || 0) * 100);
  const showProgress = !status.terminal && percent > 0;
  const libraryText = LIBRARY_TEXT[library];

  return (
    <li
      className="flex flex-col gap-2 rounded-[var(--m-radius)] border p-3"
      style={{ background: "var(--m-surface)", borderColor: "var(--m-border)" }}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 flex-1 break-words text-sm text-[var(--m-text)]">
          {task.media_name || "未命名任务"}
        </span>
        <span className="flex-shrink-0 text-xs" style={{ color: TONE_VAR[status.tone] }}>
          {status.label}
        </span>
      </div>

      {showProgress && (
        <div className="flex items-center gap-2">
          <div
            className="h-1 flex-1 overflow-hidden rounded-full"
            style={{ background: "var(--m-border)" }}
          >
            <div
              className="h-full rounded-full transition-[width] duration-500"
              style={{ width: `${percent}%`, background: "var(--m-accent)" }}
            />
          </div>
          <span className="flex-shrink-0 text-[11px] text-[var(--m-text-dim)]">{percent}%</span>
          {task.speed && (
            <span className="flex-shrink-0 text-[11px] text-[var(--m-text-dim)]">{task.speed}</span>
          )}
        </div>
      )}

      {relocate && (
        <p className="text-xs" style={{ color: TONE_VAR[relocate.tone] }}>
          {relocate.label}
        </p>
      )}

      {libraryText && (
        <p
          className="text-xs"
          style={{ color: library === "timeout" ? TONE_VAR.warning : "var(--m-text-dim)" }}
        >
          {libraryText}
        </p>
      )}

      {/* 错误原因必须显示出来，只写"失败"用户和排查的人都拿不到线索 */}
      {task.error && (
        <p className="break-words text-xs text-[var(--m-danger)]">{task.error}</p>
      )}
    </li>
  );
}
