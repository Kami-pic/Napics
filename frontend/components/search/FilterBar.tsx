// BT 搜索筛选栏 — 源下拉 + 多选筛选器 + 源专属筛选
"use client";
import React, { useMemo, useState, useRef, useEffect } from "react";
import type { FilterState, EnhancedSearchResult } from "@/types";

// ── 品牌色 ──
export const INDEXER_DOT_COLOR: Record<string, string> = {
  prowlarr: "bg-slate-400", bitsearch: "bg-blue-500", cilixiong: "bg-orange-500",
  xl720: "bg-orange-500", nyaa: "bg-purple-500", mikan: "bg-pink-500",
  yts: "bg-green-500", limetorrents: "bg-lime-500", acgrip: "bg-cyan-500",
  bangumi_moe: "bg-rose-500", eztv: "bg-sky-500", dmhy: "bg-red-500",
  "1337x": "bg-teal-500",
};
export const INDEXER_TAG_STYLE: Record<string, string> = {
  bitsearch: "bg-blue-500/15 text-blue-400", cilixiong: "bg-orange-500/15 text-orange-400",
  xl720: "bg-orange-500/15 text-orange-400", nyaa: "bg-purple-500/15 text-purple-400",
  mikan: "bg-pink-500/15 text-pink-400", yts: "bg-green-500/15 text-green-400",
  limetorrents: "bg-lime-500/15 text-lime-400", acgrip: "bg-cyan-500/15 text-cyan-400",
  bangumi_moe: "bg-rose-500/15 text-rose-400", eztv: "bg-sky-500/15 text-sky-400",
  dmhy: "bg-red-500/15 text-red-400", "1337x": "bg-teal-500/15 text-teal-400",
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

// ── 无做种数筛选的源（磁力链接源，做种数无意义）──
const NO_SEEDER_FILTER_SOURCES = new Set(["cilixiong", "xl720"]);
// ── 无做种数信息的源（ACG.RIP/Bangumi Moe seeders=0 但 size>0）──
const NO_SEEDER_INFO_SOURCES = new Set(["acgrip", "bangumi_moe", "dmhy", "mikan"]);

// ── 通用多选下拉 ──
export function MultiSelect({ label, selected, options, onChange, variant = "blue" }: {
  label: string; selected: string[];
  options: { value: string; label: string }[];
  onChange: (v: string[]) => void;
  variant?: "blue" | "emerald";
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h);
  }, []);
  const toggle = (v: string) => onChange(selected.includes(v) ? selected.filter(x => x !== v) : [...selected, v]);
  const isEmerald = variant === "emerald";
  const activeBtn = isEmerald ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" : "border-blue-500/30 bg-blue-500/10 text-blue-400";
  const activeBadge = isEmerald ? "bg-emerald-500/20" : "bg-blue-500/20";
  const activeItem = isEmerald ? "text-emerald-400 bg-emerald-500/10" : "text-blue-400 bg-blue-500/10";
  const activeCheck = isEmerald ? "border-emerald-500 bg-emerald-500/20 text-emerald-400" : "border-blue-500 bg-blue-500/20 text-blue-400";
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen(!open)}
        className={`text-[11px] px-2.5 py-1.5 rounded-lg border transition-colors flex items-center gap-1 ${
          selected.length > 0 ? activeBtn : "border-white/[0.06] bg-white/[0.04] text-slate-400 hover:text-slate-300"
        }`}>
        {label}{selected.length > 0 && <span className={`text-[9px] ${activeBadge} px-1 rounded`}>{selected.length}</span>}
        <span className="text-[8px] ml-0.5">▾</span>
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 bg-[#1a1a1a] border border-white/[0.08] rounded-lg shadow-xl z-50 min-w-[120px] py-1">
          {options.map(o => (
            <button key={o.value} onClick={() => toggle(o.value)}
              className={`w-full text-left px-3 py-1.5 text-[11px] transition-colors flex items-center gap-2 ${
                selected.includes(o.value) ? activeItem : "text-slate-400 hover:text-white hover:bg-white/[0.06]"
              }`}>
              <span className={`w-3 h-3 rounded border flex items-center justify-center text-[8px] ${
                selected.includes(o.value) ? activeCheck : "border-white/20"
              }`}>{selected.includes(o.value) ? "✓" : ""}</span>
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function NumberInput({ label, value, placeholder, onChange }: {
  label: string; value: number | null; placeholder?: string; onChange: (v: number | null) => void;
}) {
  return (
    <div className="flex items-center gap-1">
      <span className="text-[11px] text-slate-500">{label}</span>
      <input type="number" min={0} value={value === null ? "" : value} placeholder={placeholder || "0"}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        className="bg-[#1a1a1a] border border-white/[0.06] rounded-lg px-2 py-1.5 text-[11px] text-slate-300 outline-none focus:border-blue-500/50 w-[56px]" />
    </div>
  );
}

// ── "全部"模式筛选栏：直搜源下拉 + 通用筛选器 ──
interface AllFilterBarProps {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  onClear: () => void;
  btSources: { name: string; label: string; enabled: boolean }[];
  disabledSources: Set<string>;
  onToggleSource: (name: string) => void;
  availableIndexers?: string[];
}

function AllFilterBar({ filters, onChange, onClear, btSources, disabledSources, onToggleSource, availableIndexers }: AllFilterBarProps) {
  const set = <K extends keyof FilterState>(key: K, val: FilterState[K]) => onChange({ ...filters, [key]: val });
  const prowlarrEnabled = !disabledSources.has("prowlarr");

  // 直搜源选项（已启用的源）
  const sourceOptions = useMemo(() =>
    btSources.filter(s => s.enabled).map(s => ({ value: s.name, label: s.label })),
    [btSources]
  );
  // 当前显示的源（未被关闭的）
  const enabledList = useMemo(() => {
    const allEnabled = btSources.filter(s => s.enabled).map(s => s.name);
    return allEnabled.filter(name => !disabledSources.has(name));
  }, [btSources, disabledSources]);

  return (
    <div className="flex flex-wrap items-end gap-3">
      {/* 直搜源下拉（最前面）*/}
      <MultiSelect label="直搜源" selected={enabledList}
        options={sourceOptions}
        onChange={(newEnabled) => {
          // 选中=显示，取消=关闭
          const allEnabledNames = new Set(btSources.filter(s => s.enabled).map(s => s.name));
          for (const name of allEnabledNames) {
            const wasShown = !disabledSources.has(name);
            const nowShown = newEnabled.includes(name);
            if (wasShown !== nowShown) onToggleSource(name);
          }
        }} />
      {/* Prowlarr 索引器：仅 Prowlarr 开启时显示 */}
      {prowlarrEnabled && (availableIndexers?.length ?? 0) > 0 && (
        <MultiSelect label="索引器" selected={filters.indexers}
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
      <div className="flex items-center gap-1">
        <span className="text-[11px] text-slate-500">大小</span>
        <input type="number" min={0} value={filters.minSizeGb === null ? "" : filters.minSizeGb} placeholder="最小"
          onChange={(e) => set("minSizeGb", e.target.value === "" ? null : Number(e.target.value))}
          className="bg-[#1a1a1a] border border-white/[0.06] rounded-lg px-2 py-1.5 text-[11px] text-slate-300 outline-none focus:border-blue-500/50 w-[64px]" />
        <span className="text-[11px] text-slate-600">-</span>
        <input type="number" min={0} value={filters.maxSizeGb === null ? "" : filters.maxSizeGb} placeholder="最大"
          onChange={(e) => set("maxSizeGb", e.target.value === "" ? null : Number(e.target.value))}
          className="bg-[#1a1a1a] border border-white/[0.06] rounded-lg px-2 py-1.5 text-[11px] text-slate-300 outline-none focus:border-blue-500/50 w-[64px]" />
        <span className="text-[11px] text-slate-600">GB</span>
      </div>
      <NumberInput label="做种≥" value={filters.minSeeders} placeholder="0" onChange={(v) => set("minSeeders", v ?? 0)} />
      <button type="button" onClick={onClear} className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 mb-[1px]">清除</button>
    </div>
  );
}

// ── 单源模式筛选栏：根据源类型显示专属筛选器 ──
interface SourceFilterBarProps {
  source: string;
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  onClear: () => void;
  availableIndexers?: string[];
}

function SourceFilterBar({ source, filters, onChange, onClear, availableIndexers }: SourceFilterBarProps) {
  const set = <K extends keyof FilterState>(key: K, val: FilterState[K]) => onChange({ ...filters, [key]: val });
  const hasSeederFilter = !NO_SEEDER_FILTER_SOURCES.has(source) && !NO_SEEDER_INFO_SOURCES.has(source);
  const isProwlarr = source === "prowlarr";

  return (
    <div className="flex flex-wrap items-end gap-3">
      {/* Prowlarr 专属：索引器筛选 */}
      {isProwlarr && (availableIndexers?.length ?? 0) > 0 && (
        <MultiSelect label="索引器" selected={filters.indexers}
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
      <div className="flex items-center gap-1">
        <span className="text-[11px] text-slate-500">大小</span>
        <input type="number" min={0} value={filters.minSizeGb === null ? "" : filters.minSizeGb} placeholder="最小"
          onChange={(e) => set("minSizeGb", e.target.value === "" ? null : Number(e.target.value))}
          className="bg-[#1a1a1a] border border-white/[0.06] rounded-lg px-2 py-1.5 text-[11px] text-slate-300 outline-none focus:border-blue-500/50 w-[64px]" />
        <span className="text-[11px] text-slate-600">-</span>
        <input type="number" min={0} value={filters.maxSizeGb === null ? "" : filters.maxSizeGb} placeholder="最大"
          onChange={(e) => set("maxSizeGb", e.target.value === "" ? null : Number(e.target.value))}
          className="bg-[#1a1a1a] border border-white/[0.06] rounded-lg px-2 py-1.5 text-[11px] text-slate-300 outline-none focus:border-blue-500/50 w-[64px]" />
        <span className="text-[11px] text-slate-600">GB</span>
      </div>
      {/* 磁力熊/xl720/acgrip/bangumi_moe 无做种数筛选 */}
      {hasSeederFilter && (
        <NumberInput label="做种≥" value={filters.minSeeders} placeholder="0" onChange={(v) => set("minSeeders", v ?? 0)} />
      )}
      <button type="button" onClick={onClear} className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 mb-[1px]">清除</button>
    </div>
  );
}

// ── 统一导出：根据 activeSource 自动选择筛选栏 ──
interface FilterBarProps {
  activeSource: string;  // "all" 或具体源名
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  onClear: () => void;
  btSources: { name: string; label: string; enabled: boolean }[];
  disabledSources: Set<string>;
  onToggleSource: (name: string) => void;
  availableIndexers?: string[];
}

export default function FilterBar({ activeSource, filters, onChange, onClear, btSources, disabledSources, onToggleSource, availableIndexers }: FilterBarProps) {
  if (activeSource === "all") {
    return (
      <AllFilterBar
        filters={filters} onChange={onChange} onClear={onClear}
        btSources={btSources} disabledSources={disabledSources}
        onToggleSource={onToggleSource} availableIndexers={availableIndexers}
      />
    );
  }
  return (
    <SourceFilterBar
      source={activeSource} filters={filters} onChange={onChange}
      onClear={onClear} availableIndexers={availableIndexers}
    />
  );
}
