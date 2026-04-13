// 订阅管理面板：侧边抽屉，展示所有订阅，支持暂停/恢复/删除/手动搜索
"use client";
import { useState, useCallback } from "react";
import type { SubscriptionItem } from "@/hooks/useSubscriptions";
import { api } from "@/lib/api";
import { proxyUrl } from "./discoverUtils";

export interface SubscribePanelProps {
  open: boolean;
  onClose: () => void;
  subscriptions: SubscriptionItem[];
  onRefresh: () => void;
}

type FilterState = "all" | "active" | "paused" | "completed";

export default function SubscribePanel({ open, onClose, subscriptions, onRefresh }: SubscribePanelProps) {
  const [filter, setFilter] = useState<FilterState>("all");
  const [operating, setOperating] = useState<string>("");

  const filtered = filter === "all"
    ? subscriptions
    : subscriptions.filter(s => s.state === filter);

  const handleTogglePause = useCallback(async (sub: SubscriptionItem) => {
    setOperating(sub.id);
    try {
      const newState = sub.state === "paused" ? "active" : "paused";
      await api.updateSubscription(sub.id, { state: newState });
      onRefresh();
    } catch (e) {
      console.error("[SubscribePanel] 状态切换失败:", e);
    } finally {
      setOperating("");
    }
  }, [onRefresh]);

  const handleDelete = useCallback(async (sub: SubscriptionItem) => {
    setOperating(sub.id);
    try {
      await api.deleteSubscription(sub.id);
      onRefresh();
    } catch (e) {
      console.error("[SubscribePanel] 删除失败:", e);
    } finally {
      setOperating("");
    }
  }, [onRefresh]);

  const handleSearch = useCallback(async (sub: SubscriptionItem) => {
    setOperating(sub.id);
    try {
      await api.triggerSubscriptionSearch(sub.id);
    } catch (e) {
      console.error("[SubscribePanel] 搜索触发失败:", e);
    } finally {
      setOperating("");
    }
  }, []);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-[420px] h-full bg-[#141414] border-l border-white/[0.06] shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
        {/* 头部 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <h2 className="text-base font-bold text-white">我的订阅</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">✕</button>
        </div>

        {/* 筛选 */}
        <div className="flex gap-1.5 px-5 py-3 border-b border-white/[0.06]">
          {(["all", "active", "paused", "completed"] as FilterState[]).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                filter === f ? "bg-blue-600/80 text-white" : "bg-white/[0.04] text-slate-400 hover:bg-white/[0.08]"
              }`}>
              {f === "all" ? "全部" : f === "active" ? "活跃" : f === "paused" ? "已暂停" : "已完成"}
              {f === "all" && ` (${subscriptions.length})`}
            </button>
          ))}
        </div>

        {/* 列表 */}
        <div className="flex-1 overflow-y-auto px-5 py-3 space-y-3">
          {filtered.length === 0 ? (
            <p className="text-center py-12 text-xs text-slate-600">暂无订阅</p>
          ) : filtered.map(sub => (
            <SubscribeCard key={sub.id} sub={sub} operating={operating === sub.id}
              onTogglePause={() => handleTogglePause(sub)}
              onDelete={() => handleDelete(sub)}
              onSearch={() => handleSearch(sub)} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── 单个订阅卡片 ──
function SubscribeCard({ sub, operating, onTogglePause, onDelete, onSearch }: {
  sub: SubscriptionItem; operating: boolean;
  onTogglePause: () => void; onDelete: () => void; onSearch: () => void;
}) {
  const isTV = sub.type === "tv";
  const dlCount = Object.keys(sub.downloaded_episodes || {}).length;
  const hasNewRes = (sub.found_resources || []).length > 0;
  const stateLabel = sub.state === "active" ? "活跃" : sub.state === "paused" ? "已暂停" : "已完成";
  const stateColor = sub.state === "active" ? "text-emerald-400 bg-emerald-500/10"
    : sub.state === "paused" ? "text-amber-400 bg-amber-500/10"
    : "text-slate-400 bg-white/[0.06]";

  return (
    <div className={`flex gap-3 p-3 rounded-xl border transition-all ${
      operating ? "opacity-50 pointer-events-none" : ""
    } ${hasNewRes ? "border-amber-500/30 bg-amber-500/[0.03]" : "border-white/[0.06] bg-white/[0.02]"}`}>
      {/* 海报缩略图 */}
      <div className="w-12 h-[72px] flex-shrink-0 rounded-lg overflow-hidden bg-[#1a1a1a]">
        {sub.poster ? (
          <img src={proxyUrl(sub.poster)} alt={sub.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-700 text-lg">🎬</div>
        )}
      </div>
      {/* 信息 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-white truncate">{sub.title}</p>
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${stateColor}`}>{stateLabel}</span>
          {hasNewRes && <span className="text-[10px] text-amber-400">🔔</span>}
        </div>
        <div className="flex items-center gap-2 mt-1">
          {sub.year && <span className="text-[10px] text-slate-500">{sub.year}</span>}
          <span className="text-[10px] text-slate-500">{isTV ? "剧集" : "电影"}</span>
          <span className="text-[10px] text-slate-500">{sub.quality}</span>
          <span className="text-[10px] text-slate-600">{sub.mode === "auto" ? "自动" : "通知"}</span>
        </div>
        {/* 剧集进度 */}
        {isTV && sub.total_episode > 0 && (
          <div className="mt-1.5">
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                <div className="h-full bg-blue-500/80 rounded-full transition-all"
                  style={{ width: `${Math.min((dlCount / sub.total_episode) * 100, 100)}%` }} />
              </div>
              <span className="text-[10px] text-slate-500 flex-shrink-0">{dlCount}/{sub.total_episode}</span>
            </div>
          </div>
        )}
        {/* 操作按钮 */}
        <div className="flex gap-1.5 mt-2">
          <button onClick={onSearch} title="手动搜索"
            className="px-2 py-1 text-[10px] text-slate-400 bg-white/[0.04] hover:bg-white/[0.08] rounded transition-all">🔍 搜索</button>
          <button onClick={onTogglePause} title={sub.state === "paused" ? "恢复" : "暂停"}
            className="px-2 py-1 text-[10px] text-slate-400 bg-white/[0.04] hover:bg-white/[0.08] rounded transition-all">
            {sub.state === "paused" ? "▶ 恢复" : "⏸ 暂停"}
          </button>
          <button onClick={onDelete} title="删除"
            className="px-2 py-1 text-[10px] text-red-400/60 bg-white/[0.04] hover:bg-red-500/10 rounded transition-all">🗑 删除</button>
        </div>
      </div>
    </div>
  );
}
