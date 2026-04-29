// 季集完整度展示组件：从 TMDB 获取完整季/集结构，与本地文件做差集
"use client";
import { useState, useEffect } from "react";
import type { CompletenessResult, SeasonCompleteness } from "@/types";
import { api } from "@/lib/api";

interface CompletenessBarProps {
  path: string;
  folderType: string;
  tmdbId?: number;
  onSearch: (q: string, ctx?: any) => void;
  cnName?: string;
  enName?: string;
}

export function CompletenessBar({ path, folderType, tmdbId, onSearch, cnName, enName }: CompletenessBarProps) {
  const [data, setData] = useState<CompletenessResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = (refresh = false) => {
    if (!path || (folderType !== "tv" && folderType !== "season")) return;
    if (refresh) setRefreshing(true); else setLoading(true);
    api.getCompleteness(path, tmdbId, refresh)
      .then(res => { if (res.status === "ok") setData(res); })
      .catch(() => {})
      .finally(() => { setLoading(false); setRefreshing(false); });
  };

  useEffect(() => {
    setData(null);
    setExpanded(null);
    fetchData();
  }, [path, folderType, tmdbId]);

  if (folderType !== "tv" && folderType !== "season") return null;
  if (loading) return (
    <div className="flex items-center gap-2 py-1.5 px-3 rounded-lg bg-white/[0.03]">
      <div className="w-3 h-3 border-2 border-slate-500 border-t-transparent rounded-full animate-spin" />
      <span className="text-[11px] text-slate-500">检查完整度...</span>
    </div>
  );
  if (!data || !data.seasons) return null;

  const pct = data.completeness_pct ?? 0;
  const allComplete = data.seasons.every(s => s.status === "complete");
  // 本地无任何集数据时（可能路径不可达或未刮削），只显示 TMDB 总集数
  const noLocalData = (data.local_total === 0 && (data.total_episodes ?? 0) > 0);

  const handleSearchMissing = (season: SeasonCompleteness, ep?: { episode: number }) => {
    const name = cnName || enName || "";
    if (ep) {
      const q = enName
        ? `${enName} S${String(season.season_number).padStart(2, "0")}E${String(ep.episode).padStart(2, "0")}`
        : `${name} S${String(season.season_number).padStart(2, "0")}E${String(ep.episode).padStart(2, "0")}`;
      onSearch(q, { cnName, enName, folderType, seasonNumber: season.season_number, savePath: path });
    } else {
      const q = enName
        ? `${enName} S${String(season.season_number).padStart(2, "0")}`
        : `${name} Season ${season.season_number}`;
      onSearch(q, { cnName, enName, folderType, seasonNumber: season.season_number, savePath: path });
    }
  };

  return (
    <div className="space-y-2">
      {/* 总进度条 */}
      <div className="flex items-center gap-2">
        {noLocalData ? (
          <span className="text-[11px] text-slate-500 flex-1">TMDB {data.total_episodes} 集 · 本地数据待同步</span>
        ) : (
          <>
            <div className="flex-1 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${allComplete ? "bg-emerald-500" : pct > 50 ? "bg-blue-500" : "bg-amber-500"}`}
                style={{ width: `${Math.min(pct, 100)}%` }}
              />
            </div>
            <span className={`text-[11px] font-medium ${allComplete ? "text-emerald-400" : "text-slate-400"}`}>
              {allComplete ? "✓ 完整" : `${data.local_total}/${data.total_episodes} 集 (${pct}%)`}
            </span>
          </>
        )}
        <button
          onClick={() => fetchData(true)}
          disabled={refreshing}
          className="p-0.5 rounded text-slate-500 hover:text-slate-300 hover:bg-white/[0.06] transition-all disabled:opacity-50"
          title="从 TMDB 刷新季集数据（检测新季）"
        >
          <svg className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 8A6 6 0 1 1 8 2" strokeLinecap="round" />
            <path d="M8 2L11 2L11 5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      {/* 季列表 */}
      {!allComplete && !noLocalData && (
        <div className="flex flex-wrap gap-1.5">
          {data.seasons.map(s => (
            <button
              key={s.season_number}
              onClick={() => {
                if (s.status === "complete") return;
                if (s.status === "missing") { handleSearchMissing(s); return; }
                setExpanded(expanded === s.season_number ? null : s.season_number);
              }}
              className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${
                s.status === "complete"
                  ? "bg-emerald-500/15 text-emerald-400"
                  : s.status === "missing"
                    ? "bg-red-500/15 text-red-400 hover:bg-red-500/25 cursor-pointer"
                    : "bg-amber-500/15 text-amber-400 hover:bg-amber-500/25 cursor-pointer"
              }`}
              title={s.status === "complete" ? `S${s.season_number} 完整` : s.status === "missing" ? `S${s.season_number} 整季缺失 — 点击搜索` : `S${s.season_number} ${s.local_count}/${s.episode_count} 集 — 点击展开`}
            >
              S{String(s.season_number).padStart(2, "0")}
              {s.status === "complete" && " ✓"}
              {s.status === "missing" && " ✗"}
              {s.status === "partial" && ` ${s.local_count}/${s.episode_count}`}
            </button>
          ))}
        </div>
      )}

      {/* 展开的集列表 */}
      {expanded !== null && (() => {
        const season = data.seasons.find(s => s.season_number === expanded);
        if (!season || season.status === "complete") return null;
        return (
          <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-2.5 space-y-1.5">
            <div className="text-[11px] text-slate-400 font-medium">
              S{String(expanded).padStart(2, "0")} 缺失 {season.missing_episodes.length} 集
            </div>
            <div className="flex flex-wrap gap-1">
              {season.missing_episodes.map(ep => (
                <button
                  key={ep.episode}
                  onClick={() => ep.aired && handleSearchMissing(season, ep)}
                  className={`px-1.5 py-0.5 rounded text-[10px] transition-all ${
                    ep.aired
                      ? "bg-red-500/10 text-red-400 hover:bg-red-500/20 cursor-pointer"
                      : "bg-slate-500/10 text-slate-500 cursor-default"
                  }`}
                  title={ep.aired ? `E${String(ep.episode).padStart(2, "0")} ${ep.title || ""} — 点击搜索` : `E${String(ep.episode).padStart(2, "0")} ${ep.title || ""} — 未播出 (${ep.air_date})`}
                >
                  E{String(ep.episode).padStart(2, "0")}
                  {!ep.aired && " 📅"}
                </button>
              ))}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
