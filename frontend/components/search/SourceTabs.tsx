// 搜索源 Tab 切换组件 — BT 和网盘共用，显示 loading/结果条数状态
"use client";
import { useMemo } from "react";
import type { SourceStatus } from "./filterUtils";

export interface SourceTabsProps {
  type: "bt" | "pan";
  activeSource: string;  // "all" 或具体源名
  onSelect: (source: string) => void;
  enabledSources: string[];  // 已启用的源列表
  sourceLabels?: Record<string, string>;
  /** 各源搜索状态（loading/done/failed + 结果条数） */
  sourceStatuses?: Record<string, SourceStatus>;
  /** "全部"模式下的总结果数 */
  totalCount?: number;
  /** "全部"模式下是否正在搜索 */
  allSearching?: boolean;
}

export default function SourceTabs({ type, activeSource, onSelect, enabledSources, sourceLabels, sourceStatuses, totalCount, allSearching }: SourceTabsProps) {
  // Tab 列表：全部 + 已启用的源
  const tabs = useMemo(() => {
    const list = [{ name: "all", label: "全部" }];
    for (const name of enabledSources) {
      const label = sourceLabels?.[name] || name;
      if (label) {
        list.push({ name, label });
      }
    }
    return list;
  }, [enabledSources, sourceLabels]);

  return (
    <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-none">
      {tabs.map(tab => {
        const isActive = activeSource === tab.name;
        const st = tab.name === "all" ? null : sourceStatuses?.[tab.name];
        // 状态文本：loading 脉冲 / done 显示条数 / failed 显示 ✗
        const statusEl = tab.name === "all" ? (
          // "全部"tab 显示总数或搜索中
          allSearching ? <span className="text-[9px] px-1 py-0 rounded bg-blue-500/15 text-blue-400 animate-pulse ml-1">搜索中</span>
          : totalCount !== undefined && totalCount > 0 ? <span className="text-[9px] px-1 py-0 rounded bg-green-500/15 text-green-400 ml-1">✓{totalCount}</span>
          : null
        ) : st ? (
          st.status === "searching" ? <span className="text-[9px] px-1 py-0 rounded bg-blue-500/15 text-blue-400 animate-pulse ml-1">...</span>
          : st.status === "done" ? <span className="text-[9px] px-1 py-0 rounded bg-green-500/15 text-green-400 ml-1">✓{st.count}</span>
          : st.status === "failed" ? <span className="text-[9px] px-1 py-0 rounded bg-red-500/15 text-red-400 ml-1">✗</span>
          : null
        ) : null;

        return (
          <button
            key={tab.name}
            onClick={() => onSelect(tab.name)}
            className={`px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all whitespace-nowrap flex items-center gap-0.5 ${
              isActive
                ? (type === "bt" ? "bg-blue-600/20 text-blue-300 border border-blue-500/30" : "bg-emerald-600/20 text-emerald-300 border border-emerald-500/30")
                : "bg-white/[0.04] text-slate-500 border border-transparent hover:text-slate-300 hover:bg-white/[0.06]"
            }`}
          >
            {tab.label}
            {statusEl}
          </button>
        );
      })}
    </div>
  );
}
