// 回退链可视化：展示各源实际搜过哪些词，命中的高亮
"use client";
import type { SubtitleSourceStat } from "@/lib/api/subtitle";

export interface SubtitleKeywordTrailProps {
  sources: SubtitleSourceStat[];
}

export default function SubtitleKeywordTrail({ sources }: SubtitleKeywordTrailProps) {
  // 汇总所有源搜过的词，保持先后顺序；命中过的词单独标记
  const ordered: string[] = [];
  const hit = new Set<string>();
  const seen = new Set<string>();

  for (const stat of sources) {
    for (const keyword of stat.searched_keywords) {
      if (!seen.has(keyword)) {
        seen.add(keyword);
        ordered.push(keyword);
      }
    }
    if (stat.hit_keyword) hit.add(stat.hit_keyword);
  }

  if (ordered.length === 0) return null;

  // 未命中的排前面，命中的排后面 —— 视觉上呈现"回退到最后才命中"
  const trail = [
    ...ordered.filter(keyword => !hit.has(keyword)),
    ...ordered.filter(keyword => hit.has(keyword)),
  ];

  return (
    <div className="flex items-center gap-1 px-5 py-2 border-b border-white/[0.06] flex-wrap">
      <span className="text-[9px] text-slate-600 mr-0.5 flex-shrink-0">回退匹配:</span>
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
  );
}
