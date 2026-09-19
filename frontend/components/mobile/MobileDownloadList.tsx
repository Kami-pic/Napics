// 下载任务列表 + 筛选 + 快速同步恢复入口
"use client";
import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import MobileStateView from "./MobileStateView";
import MobileDownloadTaskCard from "./MobileDownloadTaskCard";
import MobileChipRow from "./MobileChipRow";
import { useMobilePluginsOptional } from "./MobileProviders";
import { api } from "@/lib/api";
import { useMobileDownloads } from "@/hooks/mobile/useMobileDownloads";
import { useMobileQuickSync } from "@/hooks/mobile/useMobileQuickSync";
import { MOBILE_ROUTES } from "@/lib/mobile/mobileRouteUtils";
import {
  countByDownloadFilter,
  matchesDownloadFilter,
  MOBILE_DOWNLOAD_FILTERS,
  type MobileDownloadFilterKey,
} from "@/lib/mobile/mobileDownloadFilters";

export default function MobileDownloadList() {
  const router = useRouter();
  const { entries, loading, loadFailed, hasAttention, refresh } = useMobileDownloads();
  const plugins = useMobilePluginsOptional();
  const hasDownload = plugins?.hasDownload ?? false;
  const sync = useMobileQuickSync();
  const [filter, setFilter] = useState<MobileDownloadFilterKey>("all");

  // 「从下载器同步」= 把 qB 里有但 napics 库里没有的任务导入 + 刷新进度，
  // 和下面的「快速同步」（入库对账 /sync）是两件事，不能合并。web 端下载管理里
  // 有同名按钮，这里把它继承过来。
  const [qbSyncing, setQbSyncing] = useState(false);
  const [qbSyncMsg, setQbSyncMsg] = useState("");
  const syncFromQb = useCallback(async () => {
    if (qbSyncing) return;
    setQbSyncing(true);
    setQbSyncMsg("");
    try {
      const res = await api.syncDownloadProgress();
      await refresh();
      const parts: string[] = [];
      if (res?.imported > 0) parts.push(`导入 ${res.imported} 个`);
      if (res?.updated > 0) parts.push(`更新 ${res.updated} 个`);
      setQbSyncMsg(parts.length > 0 ? parts.join("，") : "已同步，无新增");
    } catch {
      setQbSyncMsg("同步失败");
    } finally {
      setQbSyncing(false);
    }
  }, [qbSyncing, refresh]);

  const counts = useMemo(() => countByDownloadFilter(entries), [entries]);
  const chips = useMemo(
    () => MOBILE_DOWNLOAD_FILTERS.map(f => ({
      key: f.key,
      label: `${f.label} ${counts[f.key]}`,
      // 需处理为 0 时不强调，避免把一个空分类做成红点
      emphasize: f.key === "attention" && counts.attention > 0,
    })),
    [counts],
  );
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
      {/* 从下载器同步：导入 qB 里有但库里没有的任务并刷新进度。有下载插件才显示。 */}
      {hasDownload && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => { void syncFromQb(); }}
            disabled={qbSyncing}
            className="rounded-[var(--m-radius-sm)] px-3 text-xs disabled:opacity-50"
            style={{ minHeight: "var(--m-touch-min)", background: "var(--m-surface-raised)", color: "var(--m-text)" }}
          >
            {qbSyncing ? "同步中…" : "从下载器同步"}
          </button>
          {qbSyncMsg && <span className="text-xs text-[var(--m-text-dim)]">{qbSyncMsg}</span>}
        </div>
      )}

      {entries.length > 0 && (
        <MobileChipRow
          items={chips}
          activeKey={filter}
          onChange={key => setFilter(key as MobileDownloadFilterKey)}
          ariaLabel="任务筛选"
          semantics="radio"
        />
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
              onClick={() => router.push(MOBILE_ROUTES.resource)}
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
