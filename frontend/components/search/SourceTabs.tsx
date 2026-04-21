// 搜索源 Tab 切换组件 — BT 和网盘共用
"use client";
import { useMemo } from "react";

// 源 Tab 的中文标签映射
const BT_SOURCE_LABELS: Record<string, string> = {
  all: "全部",
  prowlarr: "Prowlarr",
  bitsearch: "Bitsearch",
  cilixiong: "磁力熊",
  xl720: "XL720",
  nyaa: "Nyaa",
  mikan: "蜜柑",
  yts: "YTS",
  limetorrents: "LimeTorrents",
  acgrip: "ACG.RIP",
  bangumi_moe: "萌番组",
};

const PAN_SOURCE_LABELS: Record<string, string> = {
  all: "全部",
  pansearch: "PanSearch",
  rrdynb: "人人电影",
  ddys: "低端影视",
  pansou: "PanSou",
  sites: "多站聚合",
  slowread: "慢读",
  wnsearch: "WnSearch",
  gogopanso: "狗狗盘搜",
  github: "GitHub",
};

export interface SourceTabsProps {
  type: "bt" | "pan";
  activeSource: string;  // "all" 或具体源名
  onSelect: (source: string) => void;
  enabledSources: string[];  // 已启用的源列表
  /** 每个源的搜索词回显（可选） */
  sourceKeywords?: Record<string, { searched: string[]; hit: string }>;
}

export default function SourceTabs({ type, activeSource, onSelect, enabledSources, sourceKeywords }: SourceTabsProps) {
  const labels = type === "bt" ? BT_SOURCE_LABELS : PAN_SOURCE_LABELS;

  // Tab 列表：全部 + 已启用的源
  const tabs = useMemo(() => {
    const list = [{ name: "all", label: "全部" }];
    for (const name of enabledSources) {
      if (labels[name]) {
        list.push({ name, label: labels[name] });
      }
    }
    return list;
  }, [enabledSources, labels]);

  return (
    <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-none">
      {tabs.map(tab => {
        const isActive = activeSource === tab.name;
        const kwInfo = sourceKeywords?.[tab.name];
        return (
          <button
            key={tab.name}
            onClick={() => onSelect(tab.name)}
            className={`px-3 py-1 rounded-lg text-[11px] font-medium transition-all whitespace-nowrap flex items-center gap-1.5 ${
              isActive
                ? (type === "bt" ? "bg-blue-600/20 text-blue-300 border border-blue-500/30" : "bg-emerald-600/20 text-emerald-300 border border-emerald-500/30")
                : "bg-white/[0.04] text-slate-500 border border-transparent hover:text-slate-300 hover:bg-white/[0.06]"
            }`}
          >
            {tab.label}
            {/* 搜索词回显：命中的词用蓝色小标签 */}
            {kwInfo?.hit && tab.name !== "all" && (
              <span className="text-[9px] px-1 py-0 rounded bg-blue-500/15 text-blue-400 max-w-[80px] truncate">
                {kwInfo.hit}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export { BT_SOURCE_LABELS, PAN_SOURCE_LABELS };
