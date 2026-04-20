// BT 搜索筛选栏 — 源开关 + 多选筛选器 + Prowlarr 索引器
"use client";
import React, { useMemo } from "react";
import type { FilterState, EnhancedSearchResult } from "@/types";

// ── 品牌色 ──
export const INDEXER_DOT_COLOR: Record<string, string> = {
  prowlarr: "bg-slate-400", bitsearch: "bg-blue-500", cilixiong: "bg-orange-500",
  xl720: "bg-orange-500", nyaa: "bg-purple-500", mikan: "bg-pink-500",
};
export const INDEXER_TAG_STYLE: Record<string, string> = {
  bitsearch: "bg-blue-500/15 text-blue-400", cilixiong: "bg-orange-500/15 text-orange-400",
  xl720: "bg-orange-500/15 text-orange-400", nyaa: "bg-purple-500/15 text-purple-400",
  mikan: "bg-pink-500/15 text-pink-400",
};

export interface SourceStatus {
  status: "idle" | "searching" | "done" | "failed";
  count: number;
}

// ── 默认筛选 ──
export const DEFAULT_FILTERS: FilterState = {
  resolution: [], source: [], videoCodec: [], audioCodec: [],
  chineseSubOnly: false, seasonPackOnly: false,
  minSizeGb: null, maxSizeGb: null, minSeeders: 0, indexers: [],
};

// ── 整季包判断 ──
const isSeasonPack = (title: string) => /S\d{2}/i.test(title) && !/E\d{2}/i.test(title);

// ── 筛选逻辑 ──
export function applyFilters(results: EnhancedSearchResult[], filters: FilterState, disabledSources?: Set<string>): EnhancedSearchResult[] {
  let list = results;
  if (disabledSources && disabledSources.size > 0) {
    list = list.filter(r => {
      const source = (r as any)._source || r.indexer;
      return !disabledSources.has(source);
    });
  }
  const isDefault = filters.resolution.length === 0 && filters.source.length === 0 &&
    filters.videoCodec.length === 0 && filters.audioCodec.length === 0 &&
    !filters.chineseSubOnly && !filters.seasonPackOnly &&
    filters.minSizeGb === null && filters.maxSizeGb === null &&
    filters.minSeeders <= 0 && filters.indexers.length === 0;
  if (isDefault) return list;
  return list.filter((r) => {
    if (filters.resolution.length > 0) {
      const res = r.quality?.resolution || "";
      if (!filters.resolution.includes(res)) return false;
    }
    if (filters.source.length > 0 && !filters.source.includes(r.quality?.source || "")) return false;
    if (filters.videoCodec.length > 0 && !filters.videoCodec.includes(r.quality?.video_codec || "")) return false;
    if (filters.audioCodec.length > 0) {
      const ac = r.quality?.audio_codec || "";
      const isSurround = r.quality?.is_surround ?? false;
      const match = filters.audioCodec.includes(ac) || (filters.audioCodec.includes("surround") && isSurround);
      if (!match) return false;
    }
    if (filters.chineseSubOnly && !r.quality?.has_chinese_sub) return false;
    if (filters.seasonPackOnly && !isSeasonPack(r.title)) return false;
    if (filters.minSizeGb !== null && r.size_gb < filters.minSizeGb) return false;
    if (filters.maxSizeGb !== null && r.size_gb > filters.maxSizeGb) return false;
    if (filters.minSeeders > 0 && r.seeders < filters.minSeeders) {
      // 磁力链接源（seeders=0 且 size=0）不受做种数筛选影响
      const isMagnetOnly = r.seeders === 0 && r.size_gb === 0;
      if (!isMagnetOnly) return false;
    }
    if (filters.indexers.length > 0) {
      // Prowlarr 索引器筛选：只对 Prowlarr 来源的结果生效，直搜源不受影响
      const source = (r as any)._source || r.indexer;
      if (source === "prowlarr" && !filters.indexers.includes(r.indexer)) return false;
    }
    return true;
  });
}

// ── 通用多选下拉组件 ──
export function MultiSelect({ label, selected, options, onChange }: {
  label: string;
  selected: string[];
  options: { value: string; label: string }[];
  onChange: (v: string[]) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const toggle = (v: string) => {
    onChange(selected.includes(v) ? selected.filter(s => s !== v) : [...selected, v]);
  };
  return (
    <div className="flex flex-col gap-1 text-xs text-slate-400 relative" ref={ref}>
      {label}
      <button type="button" onClick={() => setOpen(!open)}
        className="bg-[#1a1a1a] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 text-left min-w-[90px] h-[26px] flex items-center justify-between hover:bg-white/[0.08]">
        <span className="truncate">{selected.length === 0 ? "不限" : `已选 ${selected.length}`}</span>
        <span className="text-[10px] text-slate-600 ml-1">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="absolute top-full mt-1 left-0 w-full min-w-[130px] bg-[#1a1a1a] border border-white/[0.06] rounded-lg shadow-2xl z-[60] p-1.5 space-y-0.5 max-h-[300px] overflow-y-auto">
          {options.map((o) => (
            <label key={o.value} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-white/[0.04] transition-colors cursor-pointer">
              <input type="checkbox" checked={selected.includes(o.value)} onChange={() => toggle(o.value)}
                className="w-3.5 h-3.5 rounded border-white/10 bg-white/[0.04] text-blue-600 focus:ring-0 focus:ring-offset-0" />
              <span className="text-[12px] text-slate-300">{o.label}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 源开关栏 ──
function SourceToggleBar({ sources, statuses, disabledSources, onToggle }: {
  sources: { name: string; label: string; enabled: boolean }[];
  statuses: Record<string, SourceStatus>;
  disabledSources: Set<string>;
  onToggle: (name: string) => void;
}) {
  const enabledSources = sources.filter(s => s.enabled);
  if (!enabledSources.length) return null;
  const allDisabled = enabledSources.every(s => disabledSources.has(s.name));
  const noneDisabled = enabledSources.every(s => !disabledSources.has(s.name));
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {/* 全选/反选 */}
      <button onClick={() => { enabledSources.forEach(s => { if (allDisabled || !noneDisabled) { if (disabledSources.has(s.name)) onToggle(s.name); } else { if (!disabledSources.has(s.name)) onToggle(s.name); } }); }}
        className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] text-slate-500 hover:text-slate-300 hover:bg-white/[0.08] transition-colors"
        title={noneDisabled ? "全部关闭" : "全部开启"}>
        {noneDisabled ? "✕ 全关" : "✓ 全开"}
      </button>
      {enabledSources.map((s) => {
        const st = statuses[s.name];
        const disabled = disabledSources.has(s.name);
        const statusText = !st || st.status === "idle" ? ""
          : st.status === "searching" ? "..."
          : st.status === "done" ? `✓${st.count}` : "✗";
        const baseClass = disabled
          ? "bg-white/[0.02] text-slate-700 line-through"
          : !st || st.status === "idle" ? "bg-white/[0.04] text-slate-400"
          : st.status === "searching" ? "bg-blue-500/10 text-blue-400 animate-pulse"
          : st.status === "done" ? "bg-green-500/10 text-green-400"
          : "bg-red-500/10 text-red-400";
        return (
          <button key={s.name} onClick={() => onToggle(s.name)}
            className={`text-[10px] px-1.5 py-0.5 rounded inline-flex items-center gap-1 cursor-pointer transition-all hover:ring-1 hover:ring-white/20 ${baseClass}`}
            title={disabled ? `${s.label} 已关闭` : s.label}>
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${disabled ? "bg-slate-700" : INDEXER_DOT_COLOR[s.name] || "bg-slate-600"}`} />
            {s.label} {statusText}
          </button>
        );
      })}
    </div>
  );
}

function NumberInput({ label, value, placeholder, onChange }: {
  label: string; value: number | null; placeholder?: string; onChange: (v: number | null) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-400">
      {label}
      <input type="number" min={0} value={value === null ? "" : value} placeholder={placeholder}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        className="bg-[#1a1a1a] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 outline-none focus:border-blue-500/50 w-[80px]" />
    </label>
  );
}

interface FilterBarProps {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  onClear: () => void;
  btSources: { name: string; label: string; enabled: boolean }[];
  sourceStatuses: Record<string, SourceStatus>;
  disabledSources: Set<string>;
  onToggleSource: (name: string) => void;
  availableIndexers?: string[];
}

export default function FilterBar({ filters, onChange, onClear, btSources, sourceStatuses, disabledSources, onToggleSource, availableIndexers }: FilterBarProps) {
  const set = <K extends keyof FilterState>(key: K, val: FilterState[K]) => onChange({ ...filters, [key]: val });
  const prowlarrEnabled = !disabledSources.has("prowlarr");
  return (
    <div className="space-y-2">
      <SourceToggleBar sources={btSources} statuses={sourceStatuses} disabledSources={disabledSources} onToggle={onToggleSource} />
      <div className="flex flex-wrap items-end gap-3">
        {/* Prowlarr 索引器：仅 Prowlarr 开启时显示 */}
        {prowlarrEnabled && (availableIndexers?.length ?? 0) > 0 && (
          <MultiSelect label="Prowlarr 索引器" selected={filters.indexers}
            options={(availableIndexers || []).sort().map(i => ({ value: i, label: i }))}
            onChange={(v) => set("indexers", v)} />
        )}
        <MultiSelect label="分辨率" selected={filters.resolution}
          options={[{ value: "2160p", label: "4K" }, { value: "1080p", label: "1080p" }, { value: "720p", label: "720p" }]}
          onChange={(v) => set("resolution", v)} />
        <MultiSelect label="来源" selected={filters.source}
          options={[{ value: "Bluray", label: "Bluray" }, { value: "WEB-DL", label: "WEB-DL" }, { value: "Remux", label: "Remux" }, { value: "HDTV", label: "HDTV" }]}
          onChange={(v) => set("source", v)} />
        <MultiSelect label="视频编码" selected={filters.videoCodec}
          options={[{ value: "x265", label: "x265" }, { value: "x264", label: "x264" }, { value: "AV1", label: "AV1" }]}
          onChange={(v) => set("videoCodec", v)} />
        <MultiSelect label="音频" selected={filters.audioCodec}
          options={[
            { value: "surround", label: "🔊 环绕声 5.1+" },
            { value: "Atmos", label: "Atmos" }, { value: "TrueHD", label: "TrueHD" },
            { value: "DTS-HD", label: "DTS-HD" }, { value: "DTS", label: "DTS" }, { value: "AAC", label: "AAC" },
          ]}
          onChange={(v) => set("audioCodec", v)} />
        <MultiSelect label="特征" selected={[...(filters.chineseSubOnly ? ["chinese_sub"] : []), ...(filters.seasonPackOnly ? ["season_pack"] : [])]}
          options={[{ value: "chinese_sub", label: "含中文字幕" }, { value: "season_pack", label: "仅整季包" }]}
          onChange={(v) => {
            onChange({ ...filters, chineseSubOnly: v.includes("chinese_sub"), seasonPackOnly: v.includes("season_pack") });
          }} />
        <div className="flex flex-col gap-1 text-xs text-slate-400">
          大小(GB)
          <div className="flex items-center gap-1">
            <NumberInput label="" value={filters.minSizeGb} placeholder="最小" onChange={(v) => set("minSizeGb", v)} />
            <span className="text-slate-600">-</span>
            <NumberInput label="" value={filters.maxSizeGb} placeholder="最大" onChange={(v) => set("maxSizeGb", v)} />
          </div>
        </div>
        <NumberInput label="最低做种" value={filters.minSeeders} placeholder="0" onChange={(v) => set("minSeeders", v ?? 0)} />
        <button type="button" onClick={onClear} className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 mb-[1px]">清除</button>
      </div>
    </div>
  );
}
