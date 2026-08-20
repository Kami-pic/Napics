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
  return (
    <div className="px-5 py-2.5 border-b border-white/[0.06] space-y-2">
      {/* 来源：静态名称与动态条数分开，不拼成一串 */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[10px] text-slate-500 w-8 flex-shrink-0">来源</span>
        {SOURCE_OPTIONS.map(opt => {
          const stat = opt.key === "all" ? undefined : sources.find(s => s.source === opt.key);
          const unavailable = Boolean(stat?.error);
          const count = opt.key === "all" ? totalCount : (stat?.count ?? 0);
          const active = sourceFilter === opt.key;
          return (
            <button
              key={opt.key}
              className={`${CHIP_BASE} inline-flex items-center gap-1 ${
                active ? "bg-purple-500/20 text-purple-300" : CHIP_IDLE
              } ${unavailable ? "opacity-50" : ""}`}
              title={stat?.error ? `${opt.label}：${stat.error}` : opt.label}
              onClick={() => onSourceChange(opt.key)}
            >
              <span>{opt.label}</span>
              {unavailable ? (
                <span className="text-[9px] px-1 rounded bg-white/[0.06] text-slate-500">未配置</span>
              ) : (
                <span
                  className={`text-[9px] px-1 rounded font-mono ${
                    active ? "bg-purple-500/25 text-purple-200" : "bg-white/[0.06] text-slate-500"
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
        {totalCount > 0 && (
          <span className="text-[10px] text-slate-600 ml-auto flex-shrink-0">
            显示 {filteredCount} / 共 {totalCount}
          </span>
        )}
      </div>

      {/* 格式 */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[10px] text-slate-500 w-8 flex-shrink-0">格式</span>
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
        <span className="text-[10px] text-slate-500 w-8 flex-shrink-0">语言</span>
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
