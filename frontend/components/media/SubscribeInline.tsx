// 发现页内嵌订阅列表（作为一级 tab 内容，非侧边抽屉）
"use client";
import { useState, useCallback } from "react";
import type { SubscriptionItem } from "@/hooks/useSubscriptions";
import { api } from "@/lib/api";
import { proxyUrl } from "./discoverUtils";
import SubscribeCalendar from "./SubscribeCalendar";

export interface SubscribeInlineProps {
  subscriptions: SubscriptionItem[];
  onRefresh: () => void;
  onOpenSearch?: (item: SubscriptionItem) => void;
  view?: string;
  filter?: string;
}

export default function SubscribeInline({ subscriptions, onRefresh, onOpenSearch, view: externalView, filter: externalFilter }: SubscribeInlineProps) {
  const [operating, setOperating] = useState("");
  const view = externalView || "list";
  const filter = externalFilter || "all";

  const filtered = filter === "all" ? subscriptions : subscriptions.filter(s => s.state === filter);

  const handleAction = useCallback(async (action: "search" | "pause" | "resume" | "delete", sub: SubscriptionItem) => {
    setOperating(sub.id);
    try {
      if (action === "search") {
        const result = await api.triggerSubscriptionSearch(sub.id);
        if (result.matched > 0) onRefresh();
      } else if (action === "pause") {
        await api.updateSubscription(sub.id, { state: "paused" });
        onRefresh();
      } else if (action === "resume") {
        await api.updateSubscription(sub.id, { state: "active" });
        onRefresh();
      } else if (action === "delete") {
        await api.deleteSubscription(sub.id);
        onRefresh();
      }
    } catch (e) {
      console.error(`[SubscribeInline] ${action} 失败:`, e);
    } finally {
      setOperating("");
    }
  }, [onRefresh]);

  return (
    <div>
      {/* 日历视图 */}
      {view === "calendar" && <SubscribeCalendar />}

      {/* 列表视图 */}
      {view === "list" && (filtered.length === 0 ? (
        <p className="text-center py-16 text-sm text-slate-600">暂无订阅</p>
      ) : (
        <div className="space-y-3">
          {filtered.map(sub => {
            const isTV = sub.type === "tv";
            const dlCount = Object.keys(sub.downloaded_episodes || {}).length;
            const hasNewRes = (sub.found_resources || []).length > 0;
            const stateLabel = sub.state === "active" ? "活跃" : sub.state === "paused" ? "已暂停" : "已完成";
            const stateColor = sub.state === "active" ? "text-emerald-400 bg-emerald-500/10"
              : sub.state === "paused" ? "text-amber-400 bg-amber-500/10" : "text-slate-400 bg-white/[0.06]";
            const searchInfo = sub.last_search
              ? `搜索 ${sub.search_count || 0} 次 · ${(sub.last_search || "").slice(5, 16)}`
              : "未搜索";
            const isOp = operating === sub.id;

            return (
              <div key={sub.id} className={`p-4 rounded-xl border transition-all ${
                isOp ? "opacity-50 pointer-events-none" : ""
              } ${hasNewRes ? "border-amber-500/30 bg-amber-500/[0.03]" : "border-white/[0.06] bg-white/[0.02]"}`}>
                <div className="flex gap-4">
                  {/* 海报 */}
                  <div className="w-14 h-[84px] flex-shrink-0 rounded-lg overflow-hidden bg-[#1a1a1a]">
                    {sub.poster ? (
                      <img src={proxyUrl(sub.poster)} alt={sub.title} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-slate-700 text-xl">🎬</div>
                    )}
                  </div>
                  {/* 信息 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-white truncate">{sub.title}</p>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${stateColor}`}>{stateLabel}</span>
                      {hasNewRes && <span className="text-[10px] text-amber-400">🔔 {sub.found_resources.length}</span>}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      {sub.year && <span className="text-[11px] text-slate-500">{sub.year}</span>}
                      <span className="text-[11px] text-slate-500">{isTV ? "剧集" : "电影"}</span>
                      <span className="text-[11px] text-slate-500">{sub.quality}</span>
                      <span className="text-[11px] text-slate-600">{sub.mode === "auto" ? "自动" : "通知"}</span>
                      <span className="text-[10px] text-slate-600 ml-auto">{searchInfo}</span>
                    </div>
                    {/* 剧集进度 */}
                    {isTV && sub.total_episode > 0 && (
                      <div className="mt-2 flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                          <div className="h-full bg-blue-500/80 rounded-full transition-all"
                            style={{ width: `${Math.min((dlCount / sub.total_episode) * 100, 100)}%` }} />
                        </div>
                        <span className="text-[11px] text-slate-500 flex-shrink-0">{dlCount}/{sub.total_episode}</span>
                      </div>
                    )}
                    {/* 操作 */}
                    <div className="flex gap-2 mt-2">
                      <button onClick={() => onOpenSearch ? onOpenSearch(sub) : handleAction("search", sub)}
                        className="px-3 py-1 text-[11px] text-slate-400 bg-white/[0.04] hover:bg-white/[0.08] rounded-lg transition-all">🔍 搜索</button>
                      <button onClick={() => handleAction(sub.state === "paused" ? "resume" : "pause", sub)}
                        className="px-3 py-1 text-[11px] text-slate-400 bg-white/[0.04] hover:bg-white/[0.08] rounded-lg transition-all">
                        {sub.state === "paused" ? "▶ 恢复" : "⏸ 暂停"}
                      </button>
                      <button onClick={() => handleAction("delete", sub)}
                        className="px-3 py-1 text-[11px] text-red-400/60 bg-white/[0.04] hover:bg-red-500/10 rounded-lg transition-all">🗑 删除</button>
                    </div>
                  </div>
                </div>
                {/* 资源通知（不再展开列表，改为角标提示） */}
                {hasNewRes && (
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-[10px] text-amber-400">🔔 RSS 找到 {sub.found_resources.length} 条资源</span>
                    <button onClick={() => onOpenSearch ? onOpenSearch(sub) : handleAction("search", sub)}
                      className="text-[10px] text-blue-400 hover:text-blue-300">查看并下载 →</button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}