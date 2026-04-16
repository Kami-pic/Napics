// 网盘筛选栏 — 固定源列表 + 搜索状态
"use client";
import { useMemo } from "react";
import type { PanResult, PanSourceStatus } from "@/types";

export interface PanFilterState {
  panType: string;
  source: string;
  resolution: string;
  completeOnly: boolean;
}

export const DEFAULT_PAN_FILTERS: PanFilterState = {
  panType: "", source: "", resolution: "", completeOnly: false,
};

export function applyPanFilters(results: PanResult[], filters: PanFilterState): PanResult[] {
  const isDefault = !filters.panType && !filters.source && !filters.resolution && !filters.completeOnly;
  if (isDefault) return results;
  return results.filter((r) => {
    if (filters.panType && r.pan_type !== filters.panType) return false;
    if (filters.source && r.source !== filters.source) return false;
    if (filters.resolution && r.resolution !== filters.resolution) return false;
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
  sites: "通用站点", slowread: "慢读", wnsearch: "我能搜",
};

const SOURCE_DOT_COLOR: Record<string, string> = {
  pansearch: "bg-blue-500", pansou: "bg-cyan-500", gogopanso: "bg-green-500",
  github: "bg-slate-400", rrdynb: "bg-orange-500", ddys: "bg-purple-500",
};

export default function PanFilterBar({ filters, onChange, groups, sourceStatuses, panSources }: {
  filters: PanFilterState;
  onChange: (f: PanFilterState) => void;
  groups: Record<string, PanResult[]>;
  sourceStatuses: PanSourceStatus[];
  panSources: { name: string; label: string; enabled: boolean }[];
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

  const set = <K extends keyof PanFilterState>(key: K, val: PanFilterState[K]) =>
    onChange({ ...filters, [key]: val });
  const isFiltered = filters.panType || filters.source || filters.resolution || filters.completeOnly;

  // 构建源状态 map（从 sourceStatuses 数组）
  const statusMap = useMemo(() => {
    const m: Record<string, PanSourceStatus> = {};
    for (const s of sourceStatuses) m[s.name] = s;
    return m;
  }, [sourceStatuses]);

  return (
    <div className="space-y-2">
      {/* 源状态栏（固定列表，搜索前就显示）*/}
      <div className="flex flex-wrap items-center gap-1.5">
        {panSources.filter(s => s.enabled).map((s) => {
          const st = statusMap[s.name];
          const statusClass = !st ? "bg-white/[0.04] text-slate-600"
            : st.status === "success" ? "bg-green-500/10 text-green-400"
            : st.status === "failed" ? "bg-red-500/10 text-red-400"
            : "bg-white/[0.04] text-slate-600";
          const statusText = !st ? "" : st.status === "success" ? `✓${st.count}` : st.status === "failed" ? "✗" : "";
          return (
            <span key={s.name} className={`text-[10px] px-1.5 py-0.5 rounded inline-flex items-center gap-1 ${statusClass}`}>
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${SOURCE_DOT_COLOR[s.name] || "bg-slate-600"}`} />
              {s.label} {statusText}
            </span>
          );
        })}
      </div>
      {/* 筛选条件 */}
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          网盘
          <select value={filters.panType} onChange={(e) => set("panType", e.target.value)}
            className="bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 outline-none focus:border-emerald-500/50 min-w-[90px]">
            <option value="">不限</option>
            {panTypes.map((pt) => <option key={pt} value={pt}>{PAN_TYPE_LABELS[pt] || pt}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          来源
          <select value={filters.source} onChange={(e) => set("source", e.target.value)}
            className="bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 outline-none focus:border-emerald-500/50 min-w-[90px]">
            <option value="">不限</option>
            {panSources.filter(s => s.enabled).map((s) => <option key={s.name} value={s.name}>{s.label}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          分辨率
          <select value={filters.resolution} onChange={(e) => set("resolution", e.target.value)}
            className="bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 outline-none focus:border-emerald-500/50 min-w-[90px]">
            <option value="">不限</option>
            <option value="2160p">4K</option>
            <option value="1080p">1080p</option>
            <option value="720p">720p</option>
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-400 pt-4 cursor-pointer">
          <input type="checkbox" checked={filters.completeOnly} onChange={(e) => set("completeOnly", e.target.checked)}
            className="w-3.5 h-3.5 rounded border-white/10 bg-white/[0.04] text-emerald-600 focus:ring-0" />
          仅整季
        </label>
        {isFiltered && (
          <button onClick={() => onChange(DEFAULT_PAN_FILTERS)}
            className="text-[10px] text-slate-500 hover:text-slate-300 pt-4 underline">清除</button>
        )}
      </div>
    </div>
  );
}
