// 网盘筛选栏 — 源开关 + 多选筛选器（和 BT 侧统一）
"use client";
import { useMemo } from "react";
import type { PanResult, PanSourceStatus } from "@/types";
import { MultiSelect, INDEXER_DOT_COLOR } from "./FilterBar";

export interface PanFilterState {
  panType: string[];    // 多选：["quark", "aliyun", ...]
  resolution: string[]; // 多选：["2160p", "1080p", "720p"]
  chineseSubOnly: boolean;
  completeOnly: boolean;
}

export const DEFAULT_PAN_FILTERS: PanFilterState = {
  panType: [], resolution: [], chineseSubOnly: false, completeOnly: false,
};

export function applyPanFilters(results: PanResult[], filters: PanFilterState, disabledSources?: Set<string>): PanResult[] {
  let list = results;
  if (disabledSources && disabledSources.size > 0) {
    list = list.filter(r => !disabledSources.has(r.source));
  }
  const isDefault = filters.panType.length === 0 && filters.resolution.length === 0 && !filters.chineseSubOnly && !filters.completeOnly;
  if (isDefault) return list;
  return list.filter((r) => {
    if (filters.panType.length > 0 && !filters.panType.includes(r.pan_type)) return false;
    if (filters.resolution.length > 0 && !filters.resolution.includes(r.resolution || "")) return false;
    if (filters.completeOnly && !r.is_complete) return false;
    return true;
  });
}

export const PAN_TYPE_COLORS: Record<string, string> = {
  quark: "text-blue-400 bg-blue-400/10", aliyun: "text-orange-400 bg-orange-400/10",
  baidu: "text-green-400 bg-green-400/10", pan115: "text-purple-400 bg-purple-400/10",
  pikpak: "text-red-400 bg-red-400/10", unknown: "text-slate-400 bg-slate-400/10",
};
export const PAN_TYPE_LABELS: Record<string, string> = {
  quark: "夸克", aliyun: "阿里", baidu: "百度", pan115: "115", pikpak: "PikPak", unknown: "未知",
};
export const SOURCE_LABELS: Record<string, string> = {
  pansearch: "PanSearch", pansou: "PanSou", gogopanso: "狗狗盘搜",
  github: "GitHub仓库", rrdynb: "人人电影", ddys: "低端影视",
};

const SOURCE_DOT_COLOR: Record<string, string> = {
  pansearch: "bg-blue-500", pansou: "bg-cyan-500", gogopanso: "bg-green-500",
  github: "bg-slate-400", rrdynb: "bg-orange-500", ddys: "bg-purple-500",
};

export default function PanFilterBar({ filters, onChange, groups, sourceStatuses, panSources, disabledSources, onToggleSource }: {
  filters: PanFilterState;
  onChange: (f: PanFilterState) => void;
  groups: Record<string, PanResult[]>;
  sourceStatuses: PanSourceStatus[];
  panSources: { name: string; label: string; enabled: boolean }[];
  disabledSources: Set<string>;
  onToggleSource: (name: string) => void;
}) {
  const allResults = useMemo(() => {
    const all: PanResult[] = [];
    for (const items of Object.values(groups)) all.push(...items);
    return all;
  }, [groups]);

  const panTypes = useMemo(() => {
    const s = new Set<string>();
    for (const r of allResults) s.add(r.pan_type);
    return Array.from(s);
  }, [allResults]);

  const statusMap = useMemo(() => {
    const m: Record<string, PanSourceStatus> = {};
    for (const s of sourceStatuses) m[s.name] = s;
    return m;
  }, [sourceStatuses]);

  const isFiltered = filters.panType.length > 0 || filters.resolution.length > 0 || filters.chineseSubOnly || filters.completeOnly;

  return (
    <div className="space-y-2">
      {/* 源开关栏 */}
      <div className="flex flex-wrap items-center gap-1.5">
        {/* 全选/反选 */}
        {(() => {
          const enabledSources = panSources.filter(s => s.enabled);
          const allDisabled = enabledSources.every(s => disabledSources.has(s.name));
          const noneDisabled = enabledSources.every(s => !disabledSources.has(s.name));
          return (
            <button onClick={() => { enabledSources.forEach(s => { if (allDisabled || !noneDisabled) { if (disabledSources.has(s.name)) onToggleSource(s.name); } else { if (!disabledSources.has(s.name)) onToggleSource(s.name); } }); }}
              className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] text-slate-500 hover:text-slate-300 hover:bg-white/[0.08] transition-colors"
              title={noneDisabled ? "全部关闭" : "全部开启"}>
              {noneDisabled ? "✕ 全关" : "✓ 全开"}
            </button>
          );
        })()}
        {panSources.filter(s => s.enabled).map((s) => {
          const st = statusMap[s.name];
          const disabled = disabledSources.has(s.name);
          const statusText = !st ? "" : st.status === "success" ? `✓${st.count}` : st.status === "failed" ? "✗" : "";
          const baseClass = disabled
            ? "bg-white/[0.02] text-slate-700 line-through"
            : !st ? "bg-white/[0.04] text-slate-400"
            : st.status === "success" ? "bg-green-500/10 text-green-400"
            : st.status === "failed" ? "bg-red-500/10 text-red-400"
            : "bg-white/[0.04] text-slate-400";
          return (
            <button key={s.name} onClick={() => onToggleSource(s.name)}
              className={`text-[10px] px-1.5 py-0.5 rounded inline-flex items-center gap-1 cursor-pointer transition-all hover:ring-1 hover:ring-white/20 ${baseClass}`}
              title={disabled ? `${s.label} 已关闭` : s.label}>
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${disabled ? "bg-slate-700" : SOURCE_DOT_COLOR[s.name] || "bg-slate-600"}`} />
              {s.label} {statusText}
            </button>
          );
        })}
      </div>
      {/* 筛选条件 */}
      <div className="flex flex-wrap items-end gap-3">
        <MultiSelect label="网盘" selected={filters.panType}
          options={panTypes.map(pt => ({ value: pt, label: PAN_TYPE_LABELS[pt] || pt }))}
          onChange={(v) => onChange({ ...filters, panType: v })} />
        <MultiSelect label="分辨率" selected={filters.resolution}
          options={[{ value: "2160p", label: "4K" }, { value: "1080p", label: "1080p" }, { value: "720p", label: "720p" }]}
          onChange={(v) => onChange({ ...filters, resolution: v })} />
        <MultiSelect label="特征" selected={[...(filters.completeOnly ? ["complete"] : []), ...(filters.chineseSubOnly ? ["chinese_sub"] : [])]}
          options={[{ value: "complete", label: "仅整季" }, { value: "chinese_sub", label: "含中文字幕" }]}
          onChange={(v) => onChange({ ...filters, completeOnly: v.includes("complete"), chineseSubOnly: v.includes("chinese_sub") })} />
        {isFiltered && (
          <button onClick={() => onChange(DEFAULT_PAN_FILTERS)}
            className="text-xs text-slate-500 hover:text-slate-300 pt-4 underline">清除</button>
        )}
      </div>
    </div>
  );
}
