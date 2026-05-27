// 网盘筛选栏 — 源下拉 + 多选筛选器（和 BT 侧统一风格）
"use client";
import { useMemo } from "react";
import type { PanResult, PanSourceStatus } from "@/types";
import { MultiSelect } from "./FilterBar";

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

// ── "全部"模式筛选栏 ──
function AllPanFilterBar({ filters, onChange, groups, panSources, disabledSources, onToggleSource }: {
  filters: PanFilterState;
  onChange: (f: PanFilterState) => void;
  groups: Record<string, PanResult[]>;
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

  // 直搜源选项
  const sourceOptions = useMemo(() =>
    panSources.filter(s => s.enabled).map(s => ({ value: s.name, label: s.label })),
    [panSources]
  );
  const enabledList = useMemo(() => {
    const allEnabled = panSources.filter(s => s.enabled).map(s => s.name);
    return allEnabled.filter(name => !disabledSources.has(name));
  }, [panSources, disabledSources]);

  const isFiltered = filters.panType.length > 0 || filters.resolution.length > 0 || filters.chineseSubOnly || filters.completeOnly;

  return (
    <div className="flex flex-wrap items-end gap-3">
      {/* 直搜源下拉（最前面）*/}
      <MultiSelect label="搜索源" selected={enabledList} variant="emerald"
        options={sourceOptions}
        onChange={(newEnabled) => {
          const allEnabledNames = new Set(panSources.filter(s => s.enabled).map(s => s.name));
          for (const name of allEnabledNames) {
            const wasShown = !disabledSources.has(name);
            const nowShown = newEnabled.includes(name);
            if (wasShown !== nowShown) onToggleSource(name);
          }
        }} />
      <MultiSelect label="网盘" selected={filters.panType} variant="emerald"
        options={panTypes.map(pt => ({ value: pt, label: PAN_TYPE_LABELS[pt] || pt }))}
        onChange={(v) => onChange({ ...filters, panType: v })} />
      <MultiSelect label="分辨率" selected={filters.resolution} variant="emerald"
        options={[{ value: "2160p", label: "4K" }, { value: "1080p", label: "1080p" }, { value: "720p", label: "720p" }]}
        onChange={(v) => onChange({ ...filters, resolution: v })} />
      <MultiSelect label="特征" selected={[...(filters.completeOnly ? ["complete"] : []), ...(filters.chineseSubOnly ? ["chinese_sub"] : [])]} variant="emerald"
        options={[{ value: "complete", label: "仅整季" }, { value: "chinese_sub", label: "含中文字幕" }]}
        onChange={(v) => onChange({ ...filters, completeOnly: v.includes("complete"), chineseSubOnly: v.includes("chinese_sub") })} />
      {isFiltered && (
        <button onClick={() => onChange(DEFAULT_PAN_FILTERS)}
          className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 mb-[1px]">清除</button>
      )}
    </div>
  );
}

// ── 单源模式筛选栏（网盘单源筛选器较简单）──
function SourcePanFilterBar({ filters, onChange, groups }: {
  filters: PanFilterState;
  onChange: (f: PanFilterState) => void;
  groups: Record<string, PanResult[]>;
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

  const isFiltered = filters.panType.length > 0 || filters.resolution.length > 0 || filters.chineseSubOnly || filters.completeOnly;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <MultiSelect label="网盘" selected={filters.panType} variant="emerald"
        options={panTypes.map(pt => ({ value: pt, label: PAN_TYPE_LABELS[pt] || pt }))}
        onChange={(v) => onChange({ ...filters, panType: v })} />
      <MultiSelect label="分辨率" selected={filters.resolution} variant="emerald"
        options={[{ value: "2160p", label: "4K" }, { value: "1080p", label: "1080p" }, { value: "720p", label: "720p" }]}
        onChange={(v) => onChange({ ...filters, resolution: v })} />
      <MultiSelect label="特征" selected={[...(filters.completeOnly ? ["complete"] : []), ...(filters.chineseSubOnly ? ["chinese_sub"] : [])]} variant="emerald"
        options={[{ value: "complete", label: "仅整季" }, { value: "chinese_sub", label: "含中文字幕" }]}
        onChange={(v) => onChange({ ...filters, completeOnly: v.includes("complete"), chineseSubOnly: v.includes("chinese_sub") })} />
      {isFiltered && (
        <button onClick={() => onChange(DEFAULT_PAN_FILTERS)}
          className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 mb-[1px]">清除</button>
      )}
    </div>
  );
}

// ── 统一导出 ──
export default function PanFilterBar({ activeSource, filters, onChange, groups, sourceStatuses, panSources, disabledSources, onToggleSource }: {
  activeSource: string;  // "all" 或具体源名
  filters: PanFilterState;
  onChange: (f: PanFilterState) => void;
  groups: Record<string, PanResult[]>;
  sourceStatuses: PanSourceStatus[];
  panSources: { name: string; label: string; enabled: boolean }[];
  disabledSources: Set<string>;
  onToggleSource: (name: string) => void;
}) {
  if (activeSource === "all") {
    return (
      <AllPanFilterBar
        filters={filters} onChange={onChange} groups={groups}
        panSources={panSources} disabledSources={disabledSources}
        onToggleSource={onToggleSource}
      />
    );
  }
  return (
    <SourcePanFilterBar filters={filters} onChange={onChange} groups={groups} />
  );
}
