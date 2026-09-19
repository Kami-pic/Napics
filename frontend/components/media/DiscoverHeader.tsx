// 发现页两层 sticky 头部（一级 tab + 搜索框 + 二级推荐源 tab）
"use client";
import { useRef, useState } from "react";
import { RECOMMEND_TABS, PRIMARY_TABS, EXPLORE_TABS } from "./discoverUtils";
import type { PrimaryTab } from "./discoverUtils";
import {
  readSearchHistory,
  pushSearchHistory,
  removeSearchHistory,
} from "@/lib/mobile/searchHistory";

export interface DiscoverHeaderProps {
  primaryTab: PrimaryTab;
  setPrimaryTab: (tab: PrimaryTab) => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  exploreTab: string;
  setExploreTab: (tab: string) => void;
  isSearchMode: boolean;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  onSearch: (q: string) => void;
  onExitSearch: () => void;
  onRefresh: () => void;
  refreshing: boolean;
  scrollToDiscover: (instant?: boolean) => void;
  stickyHeaderRef: React.RefObject<HTMLDivElement | null>;
  // 订阅 tab 二级视图
  subscribeView?: string;
  onSetSubscribeView?: (view: string) => void;
  subscribeFilter?: string;
  onSetSubscribeFilter?: (filter: string) => void;
  subscribeFilterTabs?: { key: string; label: string }[];
  // 探索刷新
  onExploreRefresh?: () => void;
  exploreRefreshing?: boolean;
}

export default function DiscoverHeader({
  primaryTab, setPrimaryTab, activeTab, setActiveTab,
  exploreTab, setExploreTab,
  isSearchMode, searchQuery, setSearchQuery, onSearch, onExitSearch,
  onRefresh, refreshing, scrollToDiscover, stickyHeaderRef,
  subscribeView, onSetSubscribeView,
  subscribeFilter, onSetSubscribeFilter, subscribeFilterTabs,
  onExploreRefresh, exploreRefreshing,
}: DiscoverHeaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [history, setHistory] = useState<string[]>(() => readSearchHistory());
  const [historyOpen, setHistoryOpen] = useState(false);

  // 提交搜索：记历史 + 关下拉 + 交给父组件搜。web 与移动版共用同一份历史。
  const runSearch = (q: string) => {
    const kw = q.trim();
    if (!kw) return;
    setHistory(pushSearchHistory(kw));
    setHistoryOpen(false);
    onSearch(kw);
  };
  const pickHistory = (kw: string) => {
    setSearchQuery(kw);
    setHistory(pushSearchHistory(kw));
    setHistoryOpen(false);
    onSearch(kw);
    scrollToDiscover();
  };
  const removeHistory = (kw: string) => { setHistory(removeSearchHistory(kw)); };

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
              onKeyDown={(e) => { if (e.key === "Enter") { runSearch(searchQuery); scrollToDiscover(); } }}
              onFocus={() => { setHistoryOpen(true); scrollToDiscover(); }}
              onBlur={() => setTimeout(() => setHistoryOpen(false), 150)}
              onClick={(e) => e.stopPropagation()}
              placeholder="搜索影片..."
              className="bg-white/[0.04] border border-white/[0.06] rounded-lg pl-8 pr-3 py-1.5 text-xs text-white outline-none focus:border-blue-500/50 w-44 placeholder:text-slate-600" />
            {historyOpen && history.length > 0 && (
              <div
                onClick={(e) => e.stopPropagation()}
                className="absolute left-0 right-0 top-full z-30 mt-1 overflow-hidden rounded-lg border border-white/[0.08] bg-[#1a1a1a] shadow-xl"
              >
                {history.map((kw) => (
                  <div key={kw} className="flex items-center hover:bg-white/[0.06]">
                    <button type="button"
                      onMouseDown={(e) => { e.preventDefault(); pickHistory(kw); }}
                      className="min-w-0 flex-1 truncate px-3 py-1.5 text-left text-xs text-slate-200"
                      title={kw}>
                      {kw}
                    </button>
                    <button type="button"
                      onMouseDown={(e) => { e.preventDefault(); removeHistory(kw); }}
                      aria-label={`删除历史词 ${kw}`}
                      className="px-2 py-1.5 text-slate-600 hover:text-slate-300">
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 第二层：二级 tab（所有 primaryTab 统一在此渲染） */}
      <div className="flex gap-2 overflow-x-auto no-scrollbar py-3">
        {/* 推荐二级 tab */}
        {!isSearchMode && primaryTab === "recommend" && RECOMMEND_TABS.map((t) => (
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
        {/* 探索二级 tab */}
        {!isSearchMode && primaryTab === "explore" && EXPLORE_TABS.map(t => {
          const isActive = exploreTab === t.key;
          return (
            <button key={t.key} onClick={(e) => { e.stopPropagation(); if (t.key !== exploreTab) setExploreTab(t.key); }}
              className={`px-4 py-1.5 rounded-lg text-[13px] font-medium transition-colors whitespace-nowrap flex-shrink-0 flex items-center gap-1 ${
                isActive ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"
              }`}>
              {t.label.replace("电影", "").replace("剧集", "") || t.label}
              {t.type === "movie" && <span className="text-blue-400">电影</span>}
              {t.type === "tv" && <span className="text-green-400">剧集</span>}
              {isActive && (
                <span onClick={(e) => { e.stopPropagation(); onExploreRefresh?.(); }}
                  className={`inline-flex items-center justify-center w-4 h-4 rounded hover:bg-white/10 transition-all cursor-pointer ${exploreRefreshing ? "animate-spin" : ""}`}
                  title="刷新">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </span>
              )}
            </button>
          );
        })}
        {/* 订阅二级 tab：左边视图切换 + 右边状态筛选 */}
        {!isSearchMode && primaryTab === "subscribe" && (
          <>
            {[{ key: "list", label: "列表" }, { key: "calendar", label: "日历" }].map(t => (
              <button key={t.key}
                onClick={(e) => { e.stopPropagation(); onSetSubscribeView?.(t.key); }}
                className={`px-4 py-1.5 rounded-lg text-[13px] font-medium transition-colors whitespace-nowrap flex-shrink-0 ${
                  subscribeView === t.key ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"
                }`}>
                {t.label}
              </button>
            ))}
            <div className="flex-1" />
            {subscribeFilterTabs?.map(f => (
              <button key={f.key}
                onClick={(e) => { e.stopPropagation(); onSetSubscribeFilter?.(f.key); }}
                className={`px-2.5 py-1 rounded text-[11px] transition-colors whitespace-nowrap flex-shrink-0 ${
                  subscribeFilter === f.key ? "text-white bg-white/[0.08]" : "text-slate-600 hover:text-slate-400"
                }`}>
                {f.label}
              </button>
            ))}
          </>
        )}
        {/* 搜索模式：不可见按钮撑高度 */}
        {isSearchMode && (
          <button className="invisible px-4 py-1.5 rounded-lg text-[13px] font-medium">占位</button>
        )}
      </div>
    </div>
  );
}
