"use client";
import type { FilterState, EnhancedSearchResult } from "@/types";

// ── 分辨率数值映射（用于"不低于"比较） ──
const RESOLUTION_RANK: Record<string, number> = {
  "": 0,
  "720p": 1,
  "1080p": 2,
  "2160p": 3,
};

// ── 默认筛选状态 ──
export const DEFAULT_FILTERS: FilterState = {
  resolution: "",
  source: "",
  videoCodec: "",
  audioCodec: "",
  chineseSubOnly: false,
  minSizeGb: null,
  maxSizeGb: null,
  minSeeders: 1,
  surroundOnly: false,
  indexers: [],
};

// ── 筛选逻辑 ──
export function applyFilters(
  results: EnhancedSearchResult[],
  filters: FilterState
): EnhancedSearchResult[] {
  const isDefault =
    filters.resolution === "" &&
    filters.source === "" &&
    filters.videoCodec === "" &&
    filters.audioCodec === "" &&
    !filters.chineseSubOnly &&
    !filters.surroundOnly &&
    filters.minSizeGb === null &&
    filters.maxSizeGb === null &&
    filters.minSeeders <= 1 &&
    filters.indexers.length === 0;

  if (isDefault) return results;

  return results.filter((r) => {
    // 分辨率筛选
    if (filters.resolution) {
      const res = r.quality?.resolution || "";
      if (filters.resolution === "1080p" && res !== "1080p") return false;
      if (filters.resolution === "720p" && res !== "720p") return false;
      if (filters.resolution === ">1080p") {
        const rank = RESOLUTION_RANK[res] || 0;
        if (rank <= RESOLUTION_RANK["1080p"]) return false;
      }
      if (filters.resolution === "<720p") {
        const rank = RESOLUTION_RANK[res] || 0;
        if (rank >= RESOLUTION_RANK["720p"] || !res) return false;
      }
    }
    // 来源匹配
    if (filters.source && r.quality?.source !== filters.source) return false;
    // 视频编码匹配
    if (filters.videoCodec && r.quality?.video_codec !== filters.videoCodec) return false;
    // 音频编码匹配
    if (filters.audioCodec && r.quality?.audio_codec !== filters.audioCodec) return false;
    // 中文字幕
    if (filters.chineseSubOnly && !r.quality?.has_chinese_sub) return false;
    // 文件大小区间
    if (filters.minSizeGb !== null && r.size_gb < filters.minSizeGb) return false;
    if (filters.maxSizeGb !== null && r.size_gb > filters.maxSizeGb) return false;
    // 最低做种数
    if (filters.minSeeders > 0 && r.seeders < filters.minSeeders) return false;
    // 环绕声 5.0+
    if (filters.surroundOnly && !r.quality?.is_surround) return false;
    // 索引器多选
    if (filters.indexers.length > 0 && !filters.indexers.includes(r.indexer)) return false;

    return true;
  });
}


// ── 通用下拉组件 ──
function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-400">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 outline-none focus:border-blue-500/50 min-w-[90px]"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

// ── 数字输入组件 ──
function NumberInput({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  value: number | null;
  placeholder?: string;
  onChange: (v: number | null) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-400">
      {label}
      <input
        type="number"
        min={0}
        value={value === null ? "" : value}
        placeholder={placeholder}
        onChange={(e) => {
          const raw = e.target.value;
          onChange(raw === "" ? null : Number(raw));
        }}
        className="bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 outline-none focus:border-blue-500/50 w-[80px]"
      />
    </label>
  );
}

// ── FilterBar 组件 ──
interface FilterBarProps {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  onClear: () => void;
  availableIndexers?: string[];
}

// ── 索引器多选组件 ──
function IndexerSelect({
  selected,
  options,
  onChange,
}: {
  selected: string[];
  options: string[];
  onChange: (v: string[]) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const toggle = (indexer: string) => {
    if (selected.includes(indexer)) {
      onChange(selected.filter((s) => s !== indexer));
    } else {
      onChange([...selected, indexer]);
    }
  };

  return (
    <div className="flex flex-col gap-1 text-xs text-slate-400 relative" ref={containerRef}>
      索引器
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 text-left min-w-[120px] h-[26px] flex items-center justify-between hover:bg-white/[0.08]"
      >
        <span className="truncate">
          {selected.length === 0 ? "全部站点" : `已选 ${selected.length} 个`}
        </span>
        <span className="text-[10px] text-slate-600 ml-1">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="absolute top-full mt-1 left-0 w-full min-w-[160px] bg-[#1a1a1a] border border-white/[0.06] rounded-lg shadow-2xl z-[60] p-1.5 space-y-0.5 max-h-[300px] overflow-y-auto">
          {options.sort().map((idx) => (
            <label
              key={idx}
              className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-white/[0.04] transition-colors cursor-pointer"
            >
              <input
                type="checkbox"
                checked={selected.includes(idx)}
                onChange={() => toggle(idx)}
                className="w-3.5 h-3.5 rounded border-white/10 bg-white/[0.04] text-blue-600 focus:ring-0 focus:ring-offset-0"
              />
              <span className="text-[12px] text-slate-300 truncate">{idx}</span>
            </label>
          ))}
          {options.length === 0 && <p className="text-[10px] text-slate-600 p-2 text-center">无可用站点</p>}
        </div>
      )}
    </div>
  );
}

import React from "react";

export default function FilterBar({ filters, onChange, onClear, availableIndexers }: FilterBarProps) {
  const set = <K extends keyof FilterState>(key: K, val: FilterState[K]) =>
    onChange({ ...filters, [key]: val });

  return (
    <div className="flex flex-wrap items-end gap-3">
      <IndexerSelect
        options={availableIndexers || []}
        selected={filters.indexers}
        onChange={(v) => set("indexers", v)}
      />
      <Select
        label="分辨率"
        value={filters.resolution}
        options={[
          { value: "", label: "不限" },
          { value: "1080p", label: "1080p" },
          { value: "720p", label: "720p" },
          { value: ">1080p", label: "> 1080p" },
          { value: "<720p", label: "< 720p" },
        ]}
        onChange={(v) => set("resolution", v as FilterState["resolution"])}
      />

      <Select
        label="来源"
        value={filters.source}
        options={[
          { value: "", label: "不限" },
          { value: "Bluray", label: "Bluray" },
          { value: "WEB-DL", label: "WEB-DL" },
          { value: "Remux", label: "Remux" },
        ]}
        onChange={(v) => set("source", v as FilterState["source"])}
      />

      <Select
        label="视频编码"
        value={filters.videoCodec}
        options={[
          { value: "", label: "不限" },
          { value: "x265", label: "x265" },
          { value: "x264", label: "x264" },
        ]}
        onChange={(v) => set("videoCodec", v as FilterState["videoCodec"])}
      />

      <Select
        label="音频"
        value={filters.surroundOnly ? "surround" : filters.audioCodec}
        options={[
          { value: "", label: "不限" },
          { value: "surround", label: "🔊 环绕声 5.1+" },
          { value: "DTS", label: "DTS" },
          { value: "DTS-HD", label: "DTS-HD" },
          { value: "TrueHD", label: "TrueHD" },
          { value: "Atmos", label: "Atmos" },
          { value: "AAC", label: "AAC" },
        ]}
        onChange={(v) => {
          if (v === "surround") {
            onChange({ ...filters, audioCodec: "", surroundOnly: true });
          } else {
            onChange({ ...filters, audioCodec: v as FilterState["audioCodec"], surroundOnly: false });
          }
        }}
      />

      {/* 中文字幕开关 */}
      <label className="flex flex-col gap-1 text-xs text-slate-400">
        字幕
        <button
          type="button"
          onClick={() => set("chineseSubOnly", !filters.chineseSubOnly)}
          className={`rounded px-2 py-1 text-sm border transition-colors ${
            filters.chineseSubOnly
              ? "bg-blue-600 border-blue-500 text-white"
              : "bg-white/[0.04] border-white/[0.06] text-slate-500"
          }`}
        >
          含中文字幕
        </button>
      </label>

      <div className="flex flex-col gap-1 text-xs text-slate-400">
        大小区间(GB)
        <div className="flex items-center gap-1">
          <NumberInput
            label=""
            value={filters.minSizeGb}
            placeholder="最小"
            onChange={(v) => set("minSizeGb", v)}
          />
          <span className="text-slate-600">-</span>
          <NumberInput
            label=""
            value={filters.maxSizeGb}
            placeholder="最大"
            onChange={(v) => set("maxSizeGb", v)}
          />
        </div>
      </div>

      <NumberInput
        label="最低做种"
        value={filters.minSeeders}
        placeholder="1"
        onChange={(v) => set("minSeeders", v ?? 1)}
      />

      {/* 清除筛选 */}
      <button
        type="button"
        onClick={onClear}
        className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 mb-[1px]"
      >
        清除筛选
      </button>
    </div>
  );
}
