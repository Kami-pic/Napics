// 搜索词可视化：候选词（可点击切换）+ 各源实际回退链
"use client";
import type { SubtitleSourceStat } from "@/lib/api/subtitle";

export interface SubtitleKeywordTrailProps {
  /** 后端按「搜索升级」规则生成的候选词：中文 / 中文+英文 / 英文… */
  candidates: string[];
  sources: SubtitleSourceStat[];
  /** 当前搜索框里的词，用于高亮 */
  activeKeyword: string;
  /** 点击候选词，只用该词重搜 */
  onPick: (keyword: string) => void;
}

export default function SubtitleKeywordTrail({
  candidates, sources, activeKeyword, onPick,
}: SubtitleKeywordTrailProps) {
  // 各源实际搜过的词，保持先后顺序；命中过的单独标记
  const searched: string[] = [];
  const hit = new Set<string>();
  const seen = new Set<string>();

  for (const stat of sources) {
    for (const keyword of stat.searched_keywords) {
      if (!seen.has(keyword)) {
        seen.add(keyword);
        searched.push(keyword);
      }
    }
    if (stat.hit_keyword) hit.add(stat.hit_keyword);
  }

  // 未命中的排前面，命中的排后面 —— 呈现"回退到哪个词才命中"
  const trail = [
    ...searched.filter(keyword => !hit.has(keyword)),
    ...searched.filter(keyword => hit.has(keyword)),
  ];

  if (candidates.length === 0 && trail.length === 0) return null;

  return (
    <div className="px-5 py-2 border-b border-white/[0.06] space-y-1.5">
      {candidates.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[9px] text-slate-600 flex-shrink-0">搜索词</span>
          {candidates.map(keyword => (
            <button
              key={keyword}
              onClick={() => onPick(keyword)}
              title="用这个词单独搜"
              className={`text-[10px] px-2 py-0.5 rounded transition-colors whitespace-nowrap ${
                activeKeyword === keyword
                  ? "bg-blue-600/30 text-blue-300"
                  : "bg-white/[0.04] text-slate-500 hover:text-slate-300 hover:bg-white/[0.06]"
              }`}
            >
              {keyword}
            </button>
          ))}
        </div>
      )}

      {trail.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-[9px] text-slate-600 flex-shrink-0">回退匹配</span>
          {trail.map((keyword, index) => (
            <span key={keyword} className="flex items-center gap-1 flex-shrink-0">
              {index > 0 && <span className="text-[9px] text-slate-700">→</span>}
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap ${
                  hit.has(keyword)
                    ? "bg-blue-500/15 text-blue-400"
                    : "bg-white/[0.06] text-slate-600"
                }`}
                title={hit.has(keyword) ? "命中" : "无结果，已回退"}
              >
                {keyword}
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
