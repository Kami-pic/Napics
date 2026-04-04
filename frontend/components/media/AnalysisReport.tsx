// 全库分析报告弹窗
"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { AnalysisSummary } from "@/types";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function AnalysisReport({ open, onClose }: Props) {
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [fromCache, setFromCache] = useState(false);
  const [cacheAge, setCacheAge] = useState(0);

  useEffect(() => {
    if (open) loadReport(false);
  }, [open]);

  const loadReport = async (force: boolean) => {
    setLoading(true);
    try {
      const r = await api.getAnalysisReport(force);
      setSummary(r.summary);
      setFromCache(r.from_cache);
      setCacheAge(r.cache_age_hours);
    } catch { /* silent */ }
    setLoading(false);
  };

  if (!open) return null;

  const totalIssues = summary
    ? summary.structure_issues + summary.rename_issues + summary.scrape_issues +
      summary.quality_issues + summary.filename_issues + summary.shadow_name_issues
    : 0;
  const healthScore = summary ? Math.max(0, 100 - Math.min(totalIssues, 100)) : 0;
  const healthColor = healthScore >= 80 ? "text-green-400" : healthScore >= 50 ? "text-yellow-400" : "text-red-400";
  const healthBg = healthScore >= 80 ? "bg-green-500/10" : healthScore >= 50 ? "bg-yellow-500/10" : "bg-red-500/10";

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-8 z-50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-[#141414] border border-white/[0.06] rounded-2xl w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-white">媒体库健康报告</h2>
          <div className="flex items-center gap-2">
            {fromCache && (
              <span className="text-[10px] text-slate-600">
                缓存 {cacheAge < 1 ? "刚刚" : `${Math.round(cacheAge)}h 前`}
              </span>
            )}
            <button onClick={() => loadReport(true)} disabled={loading}
              className="text-[10px] text-blue-400 hover:text-blue-300 disabled:opacity-50">
              {loading ? "分析中..." : "刷新"}
            </button>
            <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-lg ml-2">✕</button>
          </div>
        </div>

        {loading && !summary ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-5 h-5 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin mr-3" />
            <span className="text-xs text-slate-500">正在分析全库...</span>
          </div>
        ) : summary ? (
          <div className="space-y-4">
            {/* 健康分 */}
            <div className={`${healthBg} border border-white/[0.06] rounded-xl p-4 text-center`}>
              <div className={`text-4xl font-bold ${healthColor}`}>{healthScore}</div>
              <div className="text-xs text-slate-500 mt-1">健康分（满分 100）</div>
            </div>
            {/* 各维度 */}
            <div className="grid grid-cols-3 gap-2">
              <StatCard label="文件夹" value={summary.total_folders} icon="📁" />
              <StatCard label="结构问题" value={summary.structure_issues} icon="🏗️" warn />
              <StatCard label="命名问题" value={summary.rename_issues} icon="✏️" warn />
              <StatCard label="刮削缺失" value={summary.scrape_issues} icon="🎬" warn />
              <StatCard label="质量问题" value={summary.quality_issues} icon="📊" warn />
              <StatCard label="影子名" value={summary.shadow_name_issues} icon="👤" warn />
            </div>
          </div>
        ) : (
          <p className="text-center text-slate-600 text-sm py-8">暂无数据，点击刷新开始分析</p>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, icon, warn }: { label: string; value: number; icon: string; warn?: boolean }) {
  const color = warn && value > 0 ? "text-yellow-400" : "text-slate-300";
  return (
    <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-3">
      <div className="flex items-center gap-1.5">
        <span className="text-sm">{icon}</span>
        <span className={`text-lg font-bold ${color}`}>{value}</span>
      </div>
      <div className="text-[10px] text-slate-500 mt-1">{label}</div>
    </div>
  );
}
