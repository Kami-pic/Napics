// 剧集搜索汇总表格（tv 模式）— 从 SearchModal.tsx 拆分
"use client";

import { useState } from "react";
import type { EpisodeResult, SeasonPackInfo, EnhancedSearchResult } from "@/types";

interface EpisodeTableProps {
  episodeResults: Record<number, EpisodeResult>;
  seasonPacks: SeasonPackInfo[];
  totalSizePack: number;
  totalSizeEpisode: number;
  recommendedPlan: string;
  onSelectAlternative: (ep: number, result: EnhancedSearchResult) => void;
}

export default function EpisodeTable({
  episodeResults,
  seasonPacks,
  totalSizePack,
  totalSizeEpisode,
  recommendedPlan,
  onSelectAlternative,
}: EpisodeTableProps) {
  const [expandedEp, setExpandedEp] = useState<number | null>(null);
  const episodes = Object.entries(episodeResults)
    .map(([k, v]) => ({ ep: Number(k), ...v }))
    .sort((a, b) => a.ep - b.ep);

  const foundCount = episodes.filter(e => e.status === "found").length;
  const missingCount = episodes.filter(e => e.status === "not_found").length;

  return (
    <div className="space-y-3">
      {/* 方案 PK 对比 */}
      {seasonPacks.length > 0 && (
        <div className="flex items-center gap-4 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
          <div className="flex-1 text-center">
            <p className="text-[10px] text-slate-500 mb-1">整季包方案</p>
            <p className={`text-sm font-bold ${recommendedPlan === "season_pack" ? "text-green-400" : "text-slate-400"}`}>
              {totalSizePack} GB
            </p>
            <p className="text-[10px] text-slate-600">{seasonPacks.length} 个候选</p>
          </div>
          <span className="text-slate-600 text-xs">VS</span>
          <div className="flex-1 text-center">
            <p className="text-[10px] text-slate-500 mb-1">逐集拼凑方案</p>
            <p className={`text-sm font-bold ${recommendedPlan === "per_episode" ? "text-green-400" : "text-slate-400"}`}>
              {totalSizeEpisode} GB
            </p>
            <p className="text-[10px] text-slate-600">{foundCount} 集找到 / {missingCount} 集缺失</p>
          </div>
        </div>
      )}

      {/* 逐集表格 */}
      <div className="border border-white/[0.04] rounded-lg overflow-hidden">
        <div className="grid grid-cols-[60px_1fr_80px_60px_60px] gap-2 px-3 py-2 bg-white/[0.02] text-[10px] text-slate-500 font-medium">
          <span>集号</span><span>推荐资源</span><span>大小</span><span>做种</span><span>操作</span>
        </div>
        {episodes.map(({ ep, status, recommended, alternatives }) => (
          <div key={ep}>
            <div className={`grid grid-cols-[60px_1fr_80px_60px_60px] gap-2 px-3 py-2 text-xs border-t border-white/[0.02] ${
              status === "not_found" ? "bg-red-500/5" : ""
            }`}>
              <span className="text-slate-400 font-mono">E{String(ep).padStart(2, "0")}</span>
              {status === "found" && recommended ? (
                <>
                  <span className="text-slate-300 truncate" title={recommended.quality?.display}>
                    {recommended.quality?.display || recommended.quality_tag}
                  </span>
                  <span className="text-slate-400">{recommended.size_gb} GB</span>
                  <span className={recommended.seeders > 5 ? "text-green-500" : "text-yellow-500"}>{recommended.seeders}</span>
                  <button onClick={() => setExpandedEp(expandedEp === ep ? null : ep)}
                    className="text-[10px] text-blue-400 hover:text-blue-300">
                    {alternatives.length > 0 ? `${alternatives.length}个备选` : "—"}
                  </button>
                </>
              ) : (
                <span className="col-span-4 text-red-400 font-medium">⚠ 缺失</span>
              )}
            </div>
            {/* 备选展开 */}
            {expandedEp === ep && alternatives.length > 0 && (
              <div className="px-6 py-2 bg-white/[0.01] space-y-1">
                {alternatives.slice(0, 5).map((alt, ai) => (
                  <div key={ai} className="flex items-center gap-3 text-[10px]">
                    <span className="text-slate-500">{alt.quality?.display}</span>
                    <span className="text-slate-600">{alt.size_gb} GB</span>
                    <span className="text-slate-600">做种 {alt.seeders}</span>
                    <button onClick={() => { onSelectAlternative(ep, alt); setExpandedEp(null); }}
                      className="text-blue-400 hover:text-blue-300 ml-auto">选择</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
