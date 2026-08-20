// 字幕筛选栏：来源 / 格式 / 语言
"use client";
import {
  FORMAT_OPTIONS,
  LANG_OPTIONS,
  SOURCE_OPTIONS,
  type FormatFilter,
  type LangFilter,
  type SourceFilter,
} from "./useSubtitleSearch";
import type { SubtitleSourceStat } from "@/lib/api/subtitle";

export interface SubtitleFilterBarProps {
  sourceFilter: SourceFilter;
  formatFilter: FormatFilter;
  langFilter: LangFilter;
  sources: SubtitleSourceStat[];
  filteredCount: number;
  totalCount: number;
  onSourceChange: (s: SourceFilter) => void;
  onFormatChange: (f: FormatFilter) => void;
  onLangChange: (l: LangFilter) => void;
}

const CHIP_BASE = "text-[10px] px-2 py-0.5 rounded transition-colors";
const CHIP_IDLE = "bg-white/[0.04] text-slate-500 hover:text-slate-300";

export default function SubtitleFilterBar({
  sourceFilter, formatFilter, langFilter, sources,
  filteredCount, totalCount,
  onSourceChange, onFormatChange, onLangChange,
}: SubtitleFilterBarProps) {
  const countOf = (id: string) => sources.find(s => s.source === id)?.count ?? 0;

  return (
    <div className="px-5 py-2.5 border-b border-white/[0.06] space-y-2">
      {/* 来源 */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[10px] text-slate-500 w-8">来源</span>
        {SOURCE_OPTIONS.map(opt => {
          const stat = sources.find(s => s.source === opt.key);
          const unavailable = Boolean(stat?.error);
          return (
            <button
              key={opt.key}
              className={`${CHIP_BASE} ${
                sourceFilter === opt.key ? "bg-purple-500/20 text-purple-300" : CHIP_IDLE
              } ${unavailable ? "opacity-50" : ""}`}
              title={stat?.error || undefined}
              onClick={() => onSourceChange(opt.key)}
            >
              {opt.label}
              {opt.key !== "all" && ` ${countOf(opt.key)}`}
            </button>
          );
        })}
        {totalCount > 0 && (
          <span className="text-[10px] text-slate-600 ml-auto">
            {filteredCount}/{totalCount} 条
          </span>
        )}
      </div>

      {/* 格式 */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[10px] text-slate-500 w-8">格式</span>
        {FORMAT_OPTIONS.map(opt => (
          <button
            key={opt}
            className={`${CHIP_BASE} ${
              formatFilter === opt ? "bg-blue-500/20 text-blue-400" : CHIP_IDLE
            }`}
            onClick={() => onFormatChange(opt)}
          >
            {opt}
          </button>
        ))}
      </div>

      {/* 语言 */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[10px] text-slate-500 w-8">语言</span>
        {LANG_OPTIONS.map(opt => (
          <button
            key={opt}
            className={`${CHIP_BASE} ${
              langFilter === opt ? "bg-green-500/20 text-green-400" : CHIP_IDLE
            }`}
            onClick={() => onLangChange(opt)}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );
}
