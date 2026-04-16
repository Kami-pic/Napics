// BT 搜索筛选栏 — 固定源开关 + Prowlarr 索引器筛选 + 搜索状态
"use client";
import React, { useMemo } from "react";
import type { FilterState, EnhancedSearchResult } from "@/types";

// ── 直搜源品牌色 ──
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

const RESOLUTION_RANK: Record<string, number> = { "": 0, "720p": 1, "1080p": 2, "2160p": 3 };

export const DEFAULT_FILTERS: FilterState = {
  resolution: "", source: "", videoCodec: "", audioCodec: "",
  chineseSubOnly: false, minSizeGb: null, maxSizeGb: null,
  minSeeders: 1, surroundOnly: false, indexers: [],
};

export function applyFilters(results: EnhancedSearchResult[], filters: FilterState, disabledSources?: Set<string>): EnhancedSearchResult[] {
  // 先过滤被禁用的源
  let filtered = results;
  if (disabledSources && disabledSources.size > 0) {
    filtered = filtered.filter(r => !disabledSources.has(r.indexer));
  }
  const isDefault = filters.resolution === "" && filters.source === "" && filters.videoCodec === "" &&
    filters.audioCodec === "" && !filters.chineseSubOnly && !filters.surroundOnly &&
    filters.minSizeGb === null && filters.maxSizeGb === null && filters.minSeeders <= 1 && filters.indexers.length === 0;
  if (isDefault) return filtered;
  return filtered.filter((r) => {
    if (filters.resolution) {
      const res = r.quality?.resolution || "";
      if (filters.resolution === "1080p" && res !== "1080p") return false;
      if (filters.resolution === "720p" && res !== "720p") return false;
      if (filters.resolution === ">1080p" && (RESOLUTION_RANK[res] || 0) <= RESOLUTION_RANK["1080p"]) return false;
      if (filters.resolution === "<720p" && ((RESOLUTION_RANK[res] || 0) >= RESOLUTION_RANK["720p"] || !res)) return false;
    }
    if (filters.source && r.quality?.source !== filters.source) return false;
    if (filters.videoCodec && r.quality?.video_codec !== filters.videoCodec) return false;
    if (filters.audioCodec && r.quality?.audio_codec !== filters.audioCodec) return false;
    if (filters.chineseSubOnly && !r.quality?.has_chinese_sub) return false;
    if (filters.minSizeGb !== null && r.size_gb < filters.minSizeGb) return false;
    if (filters.maxSizeGb !== null && r.size_gb > filters.maxSizeGb) return false;
    if (filters.minSeeders > 0 && r.seeders < filters.minSeeders) return false;
    if (filters.surroundOnly && !r.quality?.is_surround) return false;
    if (filters.indexers.length > 0 && !filters.indexers.includes(r.indexer)) return false;
    return true;
  });
}

// ── 源开关栏（可点击切换，搜索前就显示）──
function SourceToggleBar({ sources, statuses, disabledSources, onToggle }: {
  sources: { name: string; label: string; enabled: boolean }[];
  statuses: Record<string, SourceStatus>;
  disabledSources: Set<string>;
  onToggle: (name: string) => void;
}) {
  if (!sources.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {sources.filter(s => s.enabled).map((s) => {
        const st = statuses[s.name];
        const disabled = disabledSources.has(s.name);
        const statusText = !st || st.status === "idle" ? ""
          : st.status === "searching" ? "..."
          : st.status === "done" ? `✓${st.count}`
          : "✗";
        const baseClass = disabled
          ? "bg-white/[0.02] text-slate-700 line-through"
          : !st || st.status === "idle"
          ? "bg-white/[0.04] text-slate-400"
          : st.status === "searching"
          ? "bg-blue-500/10 text-blue-400 animate-pulse"
          : st.status === "done"
          ? "bg-green-500/10 text-green-400"
          : "bg-red-500/10 text-red-400";
        return (
          <button key={s.name} onClick={() => onToggle(s.name)}
            className={`text-[10px] px-1.5 py-0.5 rounded inline-flex items-center gap-1 cursor-pointer transition-all hover:ring-1 hover:ring-white/20 ${baseClass}`}
            title={disabled ? `${s.label} 已关闭，点击开启` : `${s.label}，点击关闭`}>
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${disabled ? "bg-slate-700" : INDEXER_DOT_COLOR[s.name] || "bg-slate-600"}`} />
            {s.label} {statusText}
          </button>
        );
      })}
    </div>
  );
}

// ── Prowlarr 索引器多选（从搜索结果动态提取）──
function IndexerSelect({ selected, options, onChange }: {
  selected: string[]; options: string[]; onChange: (v: string[]) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const toggle = (name: string) => {
    onChange(selected.includes(name) ? selected.filter(s => s !== name) : [...selected, name]);
  };
  return (
    <div className="flex flex-col gap-1 text-xs text-slate-400 relative" ref={ref}>
      Prowlarr 索引器
      <button type="button" onClick={() => setOpen(!open)}
        className="bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 text-left min-w-[120px] h-[26px] flex items-center justify-between hover:bg-white/[0.08]">
        <span className="truncate">{selected.length === 0 ? "全部站点" : `已选 ${selected.length} 个`}</span>
        <span className="text-[10px] text-slate-600 ml-1">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="absolute top-full mt-1 left-0 w-full min-w-[160px] bg-[#1a1a1a] border border-white/[0.06] rounded-lg shadow-2xl z-[60] p-1.5 space-y-0.5 max-h-[300px] overflow-y-auto">
          {options.sort().map((idx) => (
            <label key={idx} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-white/[0.04] transition-colors cursor-pointer">
              <input type="checkbox" checked={selected.includes(idx)} onChange={() => toggle(idx)}
                className="w-3.5 h-3.5 rounded border-white/10 bg-white/[0.04] text-blue-600 focus:ring-0 focus:ring-offset-0" />
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${INDEXER_DOT_COLOR[idx] || "bg-slate-600"}`} />
              <span className="text-[12px] text-slate-300 truncate">{idx}</span>
            </label>
          ))}
          {options.length === 0 && <p className="text-[10px] text-slate-600 p-2 text-center">无可用站点</p>}
        </div>
      )}
    </div>
  );
}

function Select({ label, value, options, onChange }: {
  label: string; value: string; options: { value: string; label: string }[]; onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-400">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="bg-[#1a1a1a] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 outline-none focus:border-blue-500/50 min-w-[90px]">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
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
        className="bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 outline-none focus:border-blue-500/50 w-[80px]" />
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
  return (
    <div className="space-y-2">
      {/* 源开关栏（可点击切换）*/}
      <SourceToggleBar sources={btSources} statuses={sourceStatuses} disabledSources={disabledSources} onToggle={onToggleSource} />
      {/* 筛选条件 */}
      <div className="flex flex-wrap items-end gap-3">
        <IndexerSelect options={availableIndexers || []} selected={filters.indexers} onChange={(v) => set("indexers", v)} />
        <Select label="分辨率" value={filters.resolution} options={[
          { value: "", label: "不限" }, { value: "1080p", label: "1080p" }, { value: "720p", label: "720p" },
          { value: ">1080p", label: "> 1080p" }, { value: "<720p", label: "< 720p" },
        ]} onChange={(v) => set("resolution", v as FilterState["resolution"])} />
        <Select label="来源" value={filters.source} options={[
          { value: "", label: "不限" }, { value: "Bluray", label: "Bluray" },
          { value: "WEB-DL", label: "WEB-DL" }, { value: "Remux", label: "Remux" },
        ]} onChange={(v) => set("source", v as FilterState["source"])} />
        <Select label="视频编码" value={filters.videoCodec} options={[
          { value: "", label: "不限" }, { value: "x265", label: "x265" }, { value: "x264", label: "x264" },
        ]} onChange={(v) => set("videoCodec", v as FilterState["videoCodec"])} />
        <Select label="音频" value={filters.surroundOnly ? "surround" : filters.audioCodec} options={[
          { value: "", label: "不限" }, { value: "surround", label: "🔊 环绕声 5.1+" },
          { value: "DTS", label: "DTS" }, { value: "DTS-HD", label: "DTS-HD" },
          { value: "TrueHD", label: "TrueHD" }, { value: "Atmos", label: "Atmos" }, { value: "AAC", label: "AAC" },
        ]} onChange={(v) => {
          if (v === "surround") onChange({ ...filters, audioCodec: "", surroundOnly: true });
          else onChange({ ...filters, audioCodec: v as FilterState["audioCodec"], surroundOnly: false });
        }} />
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          字幕
          <button type="button" onClick={() => set("chineseSubOnly", !filters.chineseSubOnly)}
            className={`rounded px-2 py-1 text-sm border transition-colors ${filters.chineseSubOnly ? "bg-blue-600 border-blue-500 text-white" : "bg-white/[0.04] border-white/[0.06] text-slate-500"}`}>
            含中文字幕
          </button>
        </label>
        <div className="flex flex-col gap-1 text-xs text-slate-400">
          大小区间(GB)
          <div className="flex items-center gap-1">
            <NumberInput label="" value={filters.minSizeGb} placeholder="最小" onChange={(v) => set("minSizeGb", v)} />
            <span className="text-slate-600">-</span>
            <NumberInput label="" value={filters.maxSizeGb} placeholder="最大" onChange={(v) => set("maxSizeGb", v)} />
          </div>
        </div>
        <NumberInput label="最低做种" value={filters.minSeeders} placeholder="1" onChange={(v) => set("minSeeders", v ?? 1)} />
        <button type="button" onClick={onClear} className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 mb-[1px]">清除筛选</button>
      </div>
    </div>
  );
}
