// 发现页两层 sticky 头部（一级 tab + 搜索框 + 二级推荐源 tab）
"use client";
import { useRef } from "react";
import { RECOMMEND_TABS, PRIMARY_TABS } from "./discoverUtils";
import type { PrimaryTab } from "./discoverUtils";

export interface DiscoverHeaderProps {
  primaryTab: PrimaryTab;
  setPrimaryTab: (tab: PrimaryTab) => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  isSearchMode: boolean;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  onSearch: (q: string) => void;
  onExitSearch: () => void;
  onRefresh: () => void;
  refreshing: boolean;
  scrollToDiscover: () => void;
  stickyHeaderRef: React.RefObject<HTMLDivElement | null>;
}

export default function DiscoverHeader({
  primaryTab, setPrimaryTab, activeTab, setActiveTab,
  isSearchMode, searchQuery, setSearchQuery, onSearch, onExitSearch,
  onRefresh, refreshing, scrollToDiscover, stickyHeaderRef,
}: DiscoverHeaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div ref={stickyHeaderRef} className="sticky top-0 z-20 bg-[#0f0f0f] -mx-6 px-6">
      {/* 第一层：一级 tab + 搜索框 */}
      <div className="flex items-center gap-3 py-3 border-b border-white/[0.04]">
        <div className="flex items-center gap-6 flex-shrink-0">
          {PRIMARY_TABS.map((t) => (
            <button key={t.key}
              onClick={(e) => { e.stopPropagation(); setPrimaryTab(t.key); }}
              className={`transition-colors ${
                primaryTab === t.key
                  ? "text-[15px] font-bold text-white tracking-tight"
                  : "text-[15px] font-bold text-slate-600 hover:text-slate-400 tracking-tight"
              }`}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-2 w-[240px] justify-end flex-shrink-0">
          {isSearchMode && (
            <button onClick={(e) => { e.stopPropagation(); onExitSearch(); }} className="text-xs text-slate-500 hover:text-slate-300 flex-shrink-0 whitespace-nowrap">← 返回</button>
          )}
          <div className="relative flex-shrink-0">
            <svg className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
            </svg>
            <input ref={inputRef} value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { onSearch(searchQuery); scrollToDiscover(); } }}
              onClick={(e) => e.stopPropagation()}
              placeholder="搜索影片..."
              className="bg-white/[0.04] border border-white/[0.06] rounded-lg pl-8 pr-3 py-1.5 text-xs text-white outline-none focus:border-blue-500/50 w-44 placeholder:text-slate-600" />
          </div>
        </div>
      </div>

      {/* 第二层：二级 tab */}
      {primaryTab === "recommend" && !isSearchMode && (
        <div className="flex gap-2 overflow-x-auto no-scrollbar py-3">
          {RECOMMEND_TABS.map((t) => (
            <button key={t.key}
              onClick={(e) => { e.stopPropagation(); onExitSearch(); scrollToDiscover(); if (t.key !== activeTab) setActiveTab(t.key); }}
              className={`px-4 py-1.5 rounded-lg text-[13px] font-medium transition-colors whitespace-nowrap flex-shrink-0 flex items-center gap-1 ${
                activeTab === t.key ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"
              }`}>
              {t.label}
              {activeTab === t.key && (
                <span onClick={(e) => { e.stopPropagation(); onRefresh(); }}
                  className={`inline-flex items-center justify-center w-4 h-4 rounded hover:bg-white/10 transition-all cursor-pointer ${refreshing ? "animate-spin" : ""}`}
                  title="刷新">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </span>
              )}
            </button>
          ))}
        </div>
      )}
      {primaryTab === "explore" && !isSearchMode && (
        <div className="flex gap-1 py-3">
          <span className="text-xs text-slate-500 py-1">探索筛选（阶段 2 开发中）</span>
        </div>
      )}
    </div>
  );
}
