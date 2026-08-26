// 下载任务列表 + 筛选 + 快速同步恢复入口
"use client";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import MobileStateView from "./MobileStateView";
import MobileDownloadTaskCard from "./MobileDownloadTaskCard";
import MobileDownloadFilterBar from "./MobileDownloadFilterBar";
import { useMobileDownloads } from "@/hooks/mobile/useMobileDownloads";
import { useMobileQuickSync } from "@/hooks/mobile/useMobileQuickSync";
import { MOBILE_ROUTES } from "@/lib/mobile/mobileRouteUtils";
import {
  countByDownloadFilter,
  matchesDownloadFilter,
  type MobileDownloadFilterKey,
} from "@/lib/mobile/mobileDownloadFilters";

export default function MobileDownloadList() {
  const router = useRouter();
  const { entries, loading, loadFailed, hasAttention, refresh } = useMobileDownloads();
  const sync = useMobileQuickSync();
  const [filter, setFilter] = useState<MobileDownloadFilterKey>("all");

  const counts = useMemo(() => countByDownloadFilter(entries), [entries]);
  const visible = useMemo(
    () => entries.filter(entry => matchesDownloadFilter(entry, filter)),
    [entries, filter],
  );

  // 「筛选后为空」和「一个任务都没有」是两回事，文案与出口都不同
  const filteredEmpty = entries.length > 0 && visible.length === 0;
  const state = loadFailed
    ? "error"
    : loading && entries.length === 0
      ? "loading"
      : entries.length === 0 || filteredEmpty
        ? "empty"
        : "ready";

  return (
    <div className="flex flex-col gap-4 pt-3">
      {entries.length > 0 && (
        <MobileDownloadFilterBar active={filter} counts={counts} onChange={setFilter} />
      )}

      <MobileStateView
        state={state}
        loadingText="正在读取下载任务…"
        emptyText={filteredEmpty ? "这个筛选下没有任务" : "还没有下载任务"}
        // 空态给下一步，和搜索页、媒体库的空态一个口径
        emptyAction={
          filteredEmpty ? (
            <button
              type="button"
              onClick={() => setFilter("all")}
              className="rounded-[var(--m-radius-sm)] px-4 text-sm text-[var(--m-text)]"
              style={{ minHeight: "var(--m-touch-min)", background: "var(--m-surface-raised)" }}
            >
              看全部任务
            </button>
          ) : (
            <button
              type="button"
              onClick={() => router.push(MOBILE_ROUTES.search)}
              className="rounded-[var(--m-radius-sm)] px-4 text-sm text-[var(--m-on-accent)]"
              style={{ minHeight: "var(--m-touch-min)", background: "var(--m-accent)" }}
            >
              去搜索资源
            </button>
          )
        }
        errorText="下载任务读取失败"
        onRetry={() => { void refresh(); }}
      >
        <ul className="flex flex-col gap-2">
          {visible.map(entry => (
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
