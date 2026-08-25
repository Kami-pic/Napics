// 下载任务列表 + 快速同步恢复入口
"use client";
import MobileStateView from "./MobileStateView";
import MobileDownloadTaskCard from "./MobileDownloadTaskCard";
import { useMobileDownloads } from "@/hooks/mobile/useMobileDownloads";
import { useMobileQuickSync } from "@/hooks/mobile/useMobileQuickSync";

export default function MobileDownloadList() {
  const { entries, loading, loadFailed, hasAttention, refresh } = useMobileDownloads();
  const sync = useMobileQuickSync();

  const state = loadFailed ? "error" : loading && entries.length === 0 ? "loading" : entries.length === 0 ? "empty" : "ready";

  return (
    <div className="flex flex-col gap-4 pt-3">
      <MobileStateView
        state={state}
        loadingText="正在读取下载任务…"
        emptyText="还没有下载任务"
        errorText="下载任务读取失败"
        onRetry={() => { void refresh(); }}
      >
        <ul className="flex flex-col gap-2">
          {entries.map(entry => (
            <MobileDownloadTaskCard key={entry.task.id} entry={entry} />
          ))}
        </ul>
      </MobileStateView>

      {/* 自动入库失败、归位没搬动、外部新增文件时的兜底。有需要介入的任务时才强调 */}
      <section className="flex flex-col gap-2 pt-2">
        <button
          type="button"
          onClick={() => { void sync.run(); }}
          disabled={sync.running}
          className="rounded-[var(--m-radius)] text-sm disabled:opacity-50"
          style={{
            minHeight: "var(--m-touch-min)",
            background: hasAttention ? "var(--m-accent)" : "var(--m-surface-raised)",
            color: hasAttention ? "var(--m-on-accent)" : "var(--m-text)",
          }}
        >
          {sync.running ? "同步中…" : "快速同步"}
        </button>
        {sync.message && (
          <p
            className="text-xs"
            style={{
              color: sync.phase === "failed"
                ? "var(--m-danger)"
                : sync.phase === "interrupted"
                  ? "var(--m-warning)"
                  : "var(--m-text-dim)",
            }}
          >
            {sync.message}
          </p>
        )}
      </section>
    </div>
  );
}
