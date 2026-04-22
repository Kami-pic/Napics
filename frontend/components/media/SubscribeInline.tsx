// 发现页内嵌订阅列表（两级展示：折叠态+展开态集详情）
"use client";
import { useState, useCallback, useEffect, useRef } from "react";
import type { SubscriptionItem, EpisodeInfo } from "@/hooks/useSubscriptions";
import { api } from "@/lib/api";
import { proxyUrl } from "./discoverUtils";
import SubscribeCalendar from "./SubscribeCalendar";

interface CalendarEntry {
  subscription_id: string;
  episode: number;
  air_date: string;
  episode_title: string;
  downloaded: boolean;
}

export interface SubscribeInlineProps {
  subscriptions: SubscriptionItem[];
  onRefresh: () => void;
  onOpenSearch?: (item: SubscriptionItem) => void;
  onOpenConfig?: (item: SubscriptionItem) => void;
  view?: string;
  filter?: string;
}

export default function SubscribeInline({ subscriptions, onRefresh, onOpenSearch, onOpenConfig, view: externalView, filter: externalFilter }: SubscribeInlineProps) {
  const [operating, setOperating] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [calendarData, setCalendarData] = useState<CalendarEntry[]>([]);
  const calendarLoaded = useRef(false);
  const view = externalView || "list";
  const filter = externalFilter || "all";

  const filtered = filter === "all" ? subscriptions : subscriptions.filter(s => s.state === filter);

  // 一次性拉取 calendar 数据缓存
  useEffect(() => {
    if (calendarLoaded.current) return;
    calendarLoaded.current = true;
    api.getSubscriptionCalendar()
      .then(data => setCalendarData(data || []))
      .catch(() => {});
  }, []);

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

  // 计算下一集信息（从 calendar 数据中找第一个未下载且 air_date >= today 的）
  const getNextEpisode = useCallback((sub: SubscriptionItem) => {
    if (sub.type !== "tv") return null;
    const today = new Date().toISOString().slice(0, 10);
    const subCalendar = calendarData.filter(e => e.subscription_id === sub.id);
    const next = subCalendar.find(e => !e.downloaded && e.air_date >= today);
    if (!next) return null;
    const daysUntil = Math.ceil((new Date(next.air_date).getTime() - Date.now()) / 86400000);
    const label = daysUntil === 0 ? "今天" : daysUntil === 1 ? "明天" : `${daysUntil}天后`;
    return { episode: next.episode, air_date: next.air_date, label };
  }, [calendarData]);

  // 构建展开态的集列表（合并 downloaded_episodes + calendar）
  const buildEpisodeList = useCallback((sub: SubscriptionItem) => {
    const total = sub.total_episode || 0;
    const downloaded = sub.downloaded_episodes || {};
    const subCalendar = calendarData.filter(e => e.subscription_id === sub.id);
    const calendarMap: Record<number, CalendarEntry> = {};
    for (const e of subCalendar) calendarMap[e.episode] = e;

    const today = new Date().toISOString().slice(0, 10);
    const episodes: Array<{
      num: number;
      status: "downloaded" | "airing" | "upcoming" | "unknown";
      quality?: string;
      source?: string;
      date?: string;
      episodeTitle?: string;
    }> = [];

    const maxEp = Math.max(total, ...Object.keys(downloaded).map(Number).filter(n => !isNaN(n)), ...Object.keys(calendarMap).map(Number));
    for (let i = 1; i <= maxEp; i++) {
      const dl = downloaded[String(i)] as EpisodeInfo | undefined;
      const cal = calendarMap[i];
      if (dl) {
        episodes.push({
          num: i, status: "downloaded",
          quality: dl.quality_tag || "",
          source: dl.source || "",
          date: cal?.air_date || (dl.timestamp ? dl.timestamp.slice(0, 10) : ""),
        });
      } else if (cal) {
        const isToday = cal.air_date === today;
        const isPast = cal.air_date < today;
        episodes.push({
          num: i,
          status: isPast || isToday ? "airing" : "upcoming",
          date: cal.air_date,
          episodeTitle: cal.episode_title,
        });
      } else {
        episodes.push({ num: i, status: "unknown" });
      }
    }
    return episodes;
  }, [calendarData]);

  return (
    <div>
      {view === "calendar" && <SubscribeCalendar />}

      {view === "list" && (filtered.length === 0 ? (
        <p className="text-center py-16 text-sm text-slate-600">暂无订阅</p>
      ) : (
        <div className="space-y-3">
          {filtered.map(sub => {
            const isTV = sub.type === "tv";
            const dlCount = Object.keys(sub.downloaded_episodes || {}).length;
            const hasNewRes = (sub.found_resources || []).length > 0;
            const isUpgrade = sub.purpose === "upgrade";
            const isOp = operating === sub.id;
            const isExpanded = expandedId === sub.id;
            const nextEp = isTV && !isUpgrade ? getNextEpisode(sub) : null;

            const stateLabel = sub.state === "active" ? "活跃" : sub.state === "paused" ? "已暂停" : "已完成";
            const stateColor = sub.state === "active" ? "text-emerald-400 bg-emerald-500/10"
              : sub.state === "paused" ? "text-amber-400 bg-amber-500/10" : "text-slate-400 bg-white/[0.06]";
            const sourcesLabel = (sub.sources && sub.sources.length > 0)
              ? sub.sources.slice(0, 3).join("+") + (sub.sources.length > 3 ? "..." : "") : "";
            const summary = sub.last_results_summary || (sub.last_search
              ? `搜索 ${sub.search_count || 0} 次 · ${(sub.last_search || "").slice(5, 16)}` : "未搜索");

            return (
              <div key={sub.id} className={`rounded-xl border transition-all ${
                isOp ? "opacity-50 pointer-events-none" : ""
              } ${hasNewRes ? "border-amber-500/30 bg-amber-500/[0.03]" : "border-white/[0.06] bg-white/[0.02]"}`}>
                {/* 折叠态（可点击展开） */}
                <div className="p-4 cursor-pointer" onClick={() => setExpandedId(isExpanded ? null : sub.id)}>
                  <div className="flex gap-4">
                    <div className="w-14 h-[84px] flex-shrink-0 rounded-lg overflow-hidden bg-[#1a1a1a]">
                      {sub.poster ? (
                        <img src={proxyUrl(sub.poster)} alt={sub.title} className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-slate-700 text-xl">🎬</div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-white truncate">
                          {sub.title}
                          {isTV && sub.season ? <span className="text-slate-500 ml-1">S{String(sub.season).padStart(2, "0")}</span> : null}
                        </p>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded flex-shrink-0 ${
                          isUpgrade ? "text-emerald-400 bg-emerald-500/10" : "text-blue-400 bg-blue-500/10"
                        }`}>{isUpgrade ? "⬆️洗版" : "🔄追更"}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded flex-shrink-0 ${stateColor}`}>{stateLabel}</span>
                        {hasNewRes && <span className="text-[10px] text-amber-400 flex-shrink-0">🔔 {sub.found_resources.length}</span>}
                      </div>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        {sub.year && <span className="text-[11px] text-slate-500">{sub.year}</span>}
                        <span className="text-[11px] text-slate-500">{sub.quality || "不限"}</span>
                        <span className="text-[11px] text-slate-600">{sub.mode === "auto" ? "自动" : "通知"}</span>
                        {sourcesLabel && <span className="text-[11px] text-slate-600">{sourcesLabel}</span>}
                      </div>
                      {isUpgrade ? (
                        <div className="mt-2 text-[11px] text-slate-400">
                          {sub.current_quality_score ? `${sub.current_quality_score}分` : "未知质量"}
                          {sub.target_quality && <span className="text-slate-600"> → 目标 {sub.target_quality}</span>}
                        </div>
                      ) : isTV && sub.total_episode > 0 ? (
                        <div className="mt-2 flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                            <div className="h-full bg-blue-500/80 rounded-full transition-all"
                              style={{ width: `${Math.min((dlCount / sub.total_episode) * 100, 100)}%` }} />
                          </div>
                          <span className="text-[11px] text-slate-500 flex-shrink-0">
                            {dlCount}/{sub.total_episode}
                            {nextEp && <span className="text-slate-600 ml-1">· 下集 E{String(nextEp.episode).padStart(2, "0")} {nextEp.air_date.slice(5)}({nextEp.label})</span>}
                          </span>
                        </div>
                      ) : null}
                      <p className="text-[10px] text-slate-600 mt-1 truncate">{summary}</p>
                    </div>
                  </div>
                </div>

                {/* 展开态：集详情 */}
                {isExpanded && isTV && !isUpgrade && (
                  <div className="px-4 pb-3">
                    <div className="border-t border-white/[0.06] pt-3">
                      <div className="space-y-1 max-h-[300px] overflow-y-auto">
                        {buildEpisodeList(sub).map(ep => (
                          <div key={ep.num} className={`flex items-center gap-3 px-3 py-1.5 rounded-lg text-[11px] ${
                            ep.status === "downloaded" ? "bg-emerald-500/5" :
                            ep.status === "airing" ? "bg-amber-500/5" : "bg-white/[0.02]"
                          }`}>
                            <span className="w-8 text-slate-500 flex-shrink-0">E{String(ep.num).padStart(2, "0")}</span>
                            <span className={`w-4 flex-shrink-0 ${
                              ep.status === "downloaded" ? "text-emerald-400" :
                              ep.status === "airing" ? "text-amber-400" : "text-slate-700"
                            }`}>
                              {ep.status === "downloaded" ? "✓" : ep.status === "airing" ? "⏳" : "·"}
                            </span>
                            <span className="flex-1 text-slate-400 truncate">
                              {ep.quality || ep.episodeTitle || "—"}
                            </span>
                            {ep.source && <span className="text-slate-600 flex-shrink-0">{ep.source}</span>}
                            {ep.date && <span className="text-slate-600 flex-shrink-0">{ep.date.slice(5)}</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* 操作按钮 + 资源通知 */}
                <div className="px-4 pb-4">
                  <div className="flex gap-2">
                    <button onClick={(e) => { e.stopPropagation(); onOpenSearch ? onOpenSearch(sub) : handleAction("search", sub); }}
                      className="px-3 py-1 text-[11px] text-slate-400 bg-white/[0.04] hover:bg-white/[0.08] rounded-lg transition-all">🔍 搜索</button>
                    <button onClick={(e) => { e.stopPropagation(); handleAction(sub.state === "paused" ? "resume" : "pause", sub); }}
                      className="px-3 py-1 text-[11px] text-slate-400 bg-white/[0.04] hover:bg-white/[0.08] rounded-lg transition-all">
                      {sub.state === "paused" ? "▶ 恢复" : "⏸ 暂停"}
                    </button>
                    {onOpenConfig && (
                      <button onClick={(e) => { e.stopPropagation(); onOpenConfig(sub); }}
                        className="px-3 py-1 text-[11px] text-slate-400 bg-white/[0.04] hover:bg-white/[0.08] rounded-lg transition-all">⚙ 配置</button>
                    )}
                    <button onClick={(e) => { e.stopPropagation(); handleAction("delete", sub); }}
                      className="px-3 py-1 text-[11px] text-red-400/60 bg-white/[0.04] hover:bg-red-500/10 rounded-lg transition-all">🗑</button>
                  </div>
                  {hasNewRes && (
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-[10px] text-amber-400">🔔 找到 {sub.found_resources.length} 条资源</span>
                      <button onClick={(e) => { e.stopPropagation(); onOpenSearch ? onOpenSearch(sub) : handleAction("search", sub); }}
                        className="text-[10px] text-blue-400 hover:text-blue-300">查看并下载 →</button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
