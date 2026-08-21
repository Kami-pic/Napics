// 搜索弹窗顶栏 — 从 SearchModal.tsx 拆分
"use client";
import type { EnhancedSearchResult, FilterState, PanResult, PanSourceStatus } from "@/types";
import FilterBar from "./FilterBar";
import { DEFAULT_FILTERS, type SourceStatus } from "./filterUtils";
import PanFilterBar, { PanFilterState } from "./PanFilterBar";
import SearchSettingsPanel from "./SearchSettingsPanel";
import SourceTabs from "./SourceTabs";
import type { SearchTab, SourceTabState } from "./useSearchState";

export interface SearchHeaderProps {
  // 搜索状态
  searching: boolean;
  keyword: string;
  setKeyword: (v: string) => void;
  filters: FilterState;
  setFilters: (v: FilterState) => void;
  hitKeyword: string;
  smartFilter: boolean;
  setSmartFilter: (v: boolean) => void;
  savePath: string;
  setSavePath: (v: string) => void;
  defaultSavePath: string;
  // AI
  aiRecommendEnabled: boolean;
  setAiRecommendEnabled: (v: boolean) => void;
  aiAvailable: boolean;
  // 标签
  searchTags: { label: string; keyword: string }[];
  curRes: string;
  // Tab
  activeTab: SearchTab;
  setActiveTab: (v: SearchTab) => void;
  // 网盘
  panResults: PanResult[];
  panSourceStatuses: PanSourceStatus[];
  panSearching: boolean;
  panTotal: number;
  panFilters: PanFilterState;
  setPanFilters: (v: PanFilterState) => void;
  panGroups: Record<string, PanResult[]>;
  // 设置
  showSettings: boolean;
  setShowSettings: (v: boolean) => void;
  // 源 Tab
  btActiveSource: string;
  panActiveSource: string;
  sourceTabStates: Record<string, SourceTabState>;
  sourceKeywordInfo: Record<string, { searched: string[]; hit: string }>;
  panSourceStatusMap: Record<string, SourceStatus>;
  // 源列表
  btSources: { name: string; label: string; enabled: boolean; capabilities?: string[] }[];
  panSources: { name: string; label: string; enabled: boolean; capabilities?: string[] }[];
  disabledSources: Set<string>;
  toggleSource: (name: string) => void;
  noSeederInfoSources: Set<string>;
  indexerProviderSources: Set<string>;
  availableIndexers: string[];
  // 搜索步骤
  sourceStatuses: Record<string, SourceStatus>;
  // ref
  userEditedRef: React.MutableRefObject<boolean>;
  // 搜索函数
  doSearch: (q: string) => void;
  doPanSearch: (q: string) => void;
  doSourceSearch: (source: string, kw: string) => void;
  handleBtSourceSelect: (source: string) => void;
  handlePanSourceSelect: (source: string) => void;
  // 结果（用于 Tab 切换时判断）
  results: EnhancedSearchResult[];
  // 关闭
  onClose: () => void;
}

export default function SearchHeader(props: SearchHeaderProps) {
  const {
    searching, keyword, setKeyword, filters, setFilters,
    hitKeyword, smartFilter, setSmartFilter, savePath, setSavePath, defaultSavePath,
    aiRecommendEnabled, setAiRecommendEnabled, aiAvailable,
    searchTags, curRes,
    activeTab, setActiveTab,
    panResults, panSourceStatuses, panSearching, panTotal, panFilters, setPanFilters, panGroups,
    showSettings, setShowSettings,
    btActiveSource, panActiveSource,
    sourceTabStates, sourceKeywordInfo, panSourceStatusMap,
    btSources, panSources, disabledSources, toggleSource, noSeederInfoSources, indexerProviderSources, availableIndexers,
    sourceStatuses, userEditedRef,
    doSearch, doPanSearch, doSourceSearch,
    handleBtSourceSelect, handlePanSourceSelect,
    results, onClose,
  } = props;

  return (
    <div className="p-5 border-b border-white/[0.06] space-y-3 flex-shrink-0 overflow-visible relative z-10">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-3">
          <h2 className="text-[15px] font-bold text-white">搜索资源</h2>
          {curRes && <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.06] text-slate-400">当前：{curRes}</span>}
          {hitKeyword && <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/10 text-blue-400">命中：{hitKeyword}</span>}
          {/* 搜索标签（点击快速切换搜索词）*/}
          {searchTags.length > 0 && searchTags.map((tag, ti) => (
            <button key={ti} onClick={() => { setKeyword(tag.keyword); userEditedRef.current = false; btActiveSource === "all" ? doSearch(tag.keyword) : doSourceSearch(btActiveSource, tag.keyword); }}
              className={`text-[10px] px-2 py-0.5 rounded transition-colors ${
                keyword === tag.keyword ? "bg-blue-600/30 text-blue-300" : "bg-white/[0.04] text-slate-500 hover:text-slate-300 hover:bg-white/[0.06]"
              }`}>{tag.label}</button>
          ))}
        </div>
        <div className="flex items-center gap-1 relative">
          <button onClick={() => setShowSettings(!showSettings)}
            className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all ${showSettings ? "text-blue-400 bg-blue-500/10" : "text-slate-500 hover:text-white hover:bg-white/10"}`}
            title="搜索源设置">⚙️</button>
          <button onClick={onClose} className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">✕</button>
          <SearchSettingsPanel open={showSettings} onClose={() => setShowSettings(false)} searching={searching} />
        </div>
      </div>
      <div className="flex gap-2">
        <div className="flex-1 relative">
          {/* 搜索词回显标签（input 内部，回退链用箭头连接） */}
          <div className="flex items-center w-full bg-white/[0.04] border border-white/[0.06] rounded-lg overflow-hidden focus-within:border-blue-500/50">
            {activeTab === "bt" && Object.keys(sourceKeywordInfo).length > 0 && !searching && (
              <div className="flex items-center gap-0.5 pl-2 flex-shrink-0">
                <span className="text-[9px] text-slate-600 whitespace-nowrap mr-0.5">回退匹配:</span>
                {(() => {
                  const allKws: string[] = [];
                  const hitKws = new Set<string>();
                  const seen = new Set<string>();
                  for (const info of Object.values(sourceKeywordInfo)) {
                    for (const kw of info.searched) {
                      if (!seen.has(kw)) { seen.add(kw); allKws.push(kw); }
                    }
                    if (info.hit) hitKws.add(info.hit);
                  }
                  const notHit = allKws.filter(kw => !hitKws.has(kw));
                  const hit = allKws.filter(kw => hitKws.has(kw));
                  const ordered = [...notHit, ...hit];
                  return ordered.map((kw, i) => (
                    <span key={i} className="flex items-center gap-0.5 flex-shrink-0">
                      {i > 0 && <span className="text-[9px] text-slate-700">→</span>}
                      <span className={`text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap ${
                        hitKws.has(kw) ? "bg-blue-500/15 text-blue-400" : "bg-white/[0.06] text-slate-600"
                      }`}>{kw}</span>
                    </span>
                  ));
                })()}
              </div>
            )}
            <input value={keyword} onChange={(e) => { setKeyword(e.target.value); userEditedRef.current = true; }}
              onKeyDown={(e) => { if (e.key === "Enter") { activeTab === "bt" ? (btActiveSource === "all" ? doSearch(keyword) : doSourceSearch(btActiveSource, keyword)) : doPanSearch(keyword); } }}
              placeholder="输入搜索关键词..."
              className="flex-1 bg-transparent px-3 py-2 pr-[72px] text-sm text-white outline-none placeholder:text-slate-600 min-w-[120px]" />
            {/* 搜索框内右侧按钮组：AI 推荐 + 智能过滤 */}
            {activeTab === "bt" && (
              <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-0.5">
                {aiAvailable && (
                  <button onClick={() => setAiRecommendEnabled(!aiRecommendEnabled)}
                    title={aiRecommendEnabled ? "AI 推荐已开启：搜索完成后推荐最佳资源" : "AI 推荐已关闭"}
                    className={`w-7 h-7 rounded flex items-center justify-center text-[11px] font-bold transition-colors ${aiRecommendEnabled ? "text-blue-400 hover:bg-blue-600/20" : "text-slate-600 hover:text-slate-400"}`}>
                    🤖
                  </button>
                )}
                <button onClick={() => setSmartFilter(!smartFilter)}
                  title={smartFilter ? "智能过滤已开启：隐藏不相关/枪版/死种" : "智能过滤已关闭：显示全部结果"}
                  className={`w-7 h-7 rounded flex items-center justify-center text-sm transition-colors ${smartFilter ? "text-green-400 hover:bg-green-600/20" : "text-slate-600 hover:text-slate-400"}`}>
                  {smartFilter ? "🛡️" : "🔓"}
                </button>
              </div>
            )}
          </div>
        </div>
        <button onClick={() => { activeTab === "bt" ? (btActiveSource === "all" ? doSearch(keyword) : doSourceSearch(btActiveSource, keyword)) : doPanSearch(keyword); }} disabled={searching || panSearching || (btActiveSource !== "all" && sourceTabStates[btActiveSource]?.searching)}
          className={`px-5 py-2 rounded-lg text-[12px] font-bold transition-colors whitespace-nowrap disabled:opacity-50 ${
            activeTab === "bt" ? "bg-blue-600 hover:bg-blue-500 text-white" : "bg-emerald-600 hover:bg-emerald-500 text-white"
          }`}>
          {(searching || panSearching) ? "搜索中..." : "搜索"}
        </button>
      </div>
      {/* 保存路径 + 通道切换（搜索框下方，同宽对齐） */}
      <div className="flex items-center gap-3">
        <div className="flex gap-2 flex-shrink-0">
          <button onClick={() => { setActiveTab("bt"); if (!results.length && keyword) doSearch(keyword); }}
            className={`px-8 py-2 rounded-lg text-[11px] font-bold transition-all active:scale-95 flex items-center gap-2 ${
              activeTab === "bt" ? "bg-blue-600 text-white shadow-lg shadow-blue-500/20" : "bg-white/[0.06] text-slate-400 hover:bg-white/10"
            }`}>
            <span>🧲</span> BT / 磁力
          </button>
          <button onClick={() => { setActiveTab("pan"); if (!panResults.length && keyword) doPanSearch(keyword); }}
            className={`px-8 py-2 rounded-lg text-[11px] font-bold transition-all active:scale-95 flex items-center gap-2 ${
              activeTab === "pan" ? "bg-emerald-600 text-white shadow-lg shadow-emerald-500/20" : "bg-white/[0.06] text-slate-400 hover:bg-white/10"
            }`}>
            <span>☁️</span> 网盘资源
          </button>
        </div>
        
        <div className="w-px h-6 bg-white/[0.06] mx-1" />
        
        <div className="flex-1 relative group">
          <input value={savePath} onChange={(e) => setSavePath(e.target.value)}
            placeholder={defaultSavePath ? `保存到：${defaultSavePath}` : "保存到：下载保存路径..."}
            className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-blue-500/50 font-mono transition-all group-hover:bg-white/[0.06]"
            title={savePath || defaultSavePath} />
        </div>
      </div>
      {/* 分割线：将 SourceTabs + 筛选器 和上面的搜索区域分开 */}
      <div className="border-t border-white/[0.04] pt-3 -mx-5 px-5 flex flex-col items-start gap-2">
      {activeTab === "bt" && (
        <SourceTabs
          type="bt"
          activeSource={btActiveSource}
          onSelect={handleBtSourceSelect}
          enabledSources={btSources.filter(s => s.enabled).map(s => s.name)}
          sourceLabels={Object.fromEntries(btSources.map(s => [s.name, s.label]))}
          sourceStatuses={sourceStatuses}
          totalCount={results.length}
          allSearching={searching}
        />
      )}
      {activeTab === "bt" && (
        <FilterBar
          activeSource={btActiveSource}
          filters={filters}
          onChange={setFilters}
          onClear={() => setFilters(DEFAULT_FILTERS)}
          btSources={btSources}
          disabledSources={disabledSources}
          onToggleSource={toggleSource}
          availableIndexers={availableIndexers}
          noSeederInfoSources={noSeederInfoSources}
          indexerProviderSources={indexerProviderSources}
        />
      )}
      {activeTab === "pan" && (
        <SourceTabs
          type="pan"
          activeSource={panActiveSource}
          onSelect={handlePanSourceSelect}
          enabledSources={panSources.filter(s => s.enabled).map(s => s.name)}
          sourceLabels={Object.fromEntries(panSources.map(s => [s.name, s.label]))}
          sourceStatuses={panSourceStatusMap}
          totalCount={panTotal}
          allSearching={panSearching}
        />
      )}
      {activeTab === "pan" && (
        <PanFilterBar activeSource={panActiveSource} filters={panFilters} onChange={setPanFilters} groups={panGroups} sourceStatuses={panSourceStatuses} panSources={panSources} disabledSources={disabledSources} onToggleSource={toggleSource} />
      )}
      </div>
    </div>
  );
}
