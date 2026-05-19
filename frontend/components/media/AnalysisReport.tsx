// 全库分析报告弹窗（含 AI 诊断）
"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { AnalysisSummary, AIDiagnosisResult } from "@/types";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function AnalysisReport({ open, onClose }: Props) {
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [fromCache, setFromCache] = useState(false);
  const [cacheAge, setCacheAge] = useState(0);
  const [aiDiag, setAiDiag] = useState<AIDiagnosisResult | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [tab, setTab] = useState<"rules" | "ai">("rules");

  useEffect(() => {
    if (open) { loadReport(false); setAiDiag(null); setAiError(""); setTab("rules"); }
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

  const runAiDiagnosis = async () => {
    setAiLoading(true);
    setAiError("");
    try {
      const r = await api.aiDiagnosis();
      setAiDiag(r);
    } catch (e: any) {
      setAiError(e.message?.includes("400") ? "AI 诊断未启用，请先在设置页配置 AI" : "诊断失败，请稍后重试");
    }
    setAiLoading(false);
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
          <div className="flex items-center gap-4">
            <h2 className="text-base font-semibold text-white">媒体库健康报告</h2>
            <div className="flex gap-1">
              <button onClick={() => setTab("rules")}
                className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all ${tab === "rules" ? "bg-blue-600/20 text-blue-400" : "text-slate-500 hover:text-slate-300"}`}>
                规则检查
              </button>
              <button onClick={() => { setTab("ai"); if (!aiDiag && !aiLoading) runAiDiagnosis(); }}
                className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all ${tab === "ai" ? "bg-blue-600/20 text-blue-400" : "text-slate-500 hover:text-slate-300"}`}>
                🤖 AI 诊断
              </button>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {tab === "rules" && fromCache && (
              <span className="text-[10px] text-slate-600">
                缓存 {cacheAge < 1 ? "刚刚" : `${Math.round(cacheAge)}h 前`}
              </span>
            )}
            {tab === "rules" && (
              <button onClick={() => loadReport(true)} disabled={loading}
                className="text-[10px] text-blue-400 hover:text-blue-300 disabled:opacity-50">
                {loading ? "分析中..." : "刷新"}
              </button>
            )}
            <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-lg ml-2">✕</button>
          </div>
        </div>

        {tab === "rules" ? (
          <>
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
              <StatCard label="标准化名称" value={summary.shadow_name_issues} icon="👤" warn />
            </div>
          </div>
        ) : (
          <p className="text-center text-slate-600 text-sm py-8">暂无数据，点击刷新开始分析</p>
        )}
          </>
        ) : (
          /* AI 诊断 tab */
          <div>
            {aiLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-5 h-5 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin mr-3" />
                <span className="text-xs text-slate-500">AI 正在分析媒体库（约 30 秒）...</span>
              </div>
            ) : aiError ? (
              <div className="text-center py-12">
                <p className="text-sm text-red-400 mb-3">{aiError}</p>
                <button onClick={runAiDiagnosis} className="text-[10px] text-blue-400 hover:text-blue-300">重试</button>
              </div>
            ) : aiDiag ? (
              <div className="space-y-4">
                {/* AI 健康分 */}
                <div className={`${aiDiag.health_score >= 80 ? "bg-green-500/10" : aiDiag.health_score >= 50 ? "bg-yellow-500/10" : "bg-red-500/10"} border border-white/[0.06] rounded-xl p-4 text-center`}>
                  <div className={`text-4xl font-bold ${aiDiag.health_score >= 80 ? "text-green-400" : aiDiag.health_score >= 50 ? "text-yellow-400" : "text-red-400"}`}>
                    {aiDiag.health_score}
                  </div>
                  <div className="text-xs text-slate-500 mt-1">🤖 AI 健康评分</div>
                </div>
                {/* AI 总结 */}
                <p className="text-xs text-slate-400 leading-relaxed">{aiDiag.summary}</p>
                {/* 优先建议 */}
                <div className="space-y-2">
                  {aiDiag.priorities?.map((p, i) => (
                    <div key={i} className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`w-2 h-2 rounded-full ${p.severity === "high" ? "bg-red-400" : p.severity === "medium" ? "bg-yellow-400" : "bg-blue-400"}`} />
                        <span className="text-xs font-medium text-slate-300">{p.category}</span>
                        <span className="text-[10px] text-slate-500 ml-auto">{p.count} 项</span>
                      </div>
                      <p className="text-[10px] text-slate-500">{p.suggestion}</p>
                    </div>
                  ))}
                </div>
                <button onClick={runAiDiagnosis} disabled={aiLoading}
                  className="w-full text-[10px] text-slate-500 hover:text-slate-300 py-2">重新诊断</button>
              </div>
            ) : (
              <div className="text-center py-12">
                <span className="text-4xl mb-4 block opacity-30">🤖</span>
                <p className="text-sm text-slate-500 mb-4">AI 将分析你的媒体库并给出改进建议</p>
                <button onClick={runAiDiagnosis}
                  className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-xl text-sm font-medium transition-all">
                  开始 AI 诊断
                </button>
              </div>
            )}
          </div>
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
