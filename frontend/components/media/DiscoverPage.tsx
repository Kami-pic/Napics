// 发现页：多榜单推荐 + 探索筛选 + 搜索（瘦壳组件，编排两个 hook + 渲染布局）
// 核心优化：已加载的 tab 内容保持在 DOM 中（display:none），切 tab 时图片不重新加载
"use client";
import type { DoubanHotItem } from "@/types";
import DiscoverCard from "./DiscoverCard";
import SkeletonGrid from "./SkeletonGrid";
import ExpandDetail from "./ExpandDetail";
import DiscoverHeader from "./DiscoverHeader";
import ExplorePage from "./ExplorePage";
import RecommendTabContent from "./RecommendTabContent";
import SubscribeInline from "./SubscribeInline";
import SearchModal from "@/components/search/SearchModal";
import SubscribeConfigModal from "./SubscribeConfigModal";
import { useDiscoverState } from "./useDiscoverState";
import { useDiscoverSubscribe } from "./useDiscoverSubscribe";

interface DiscoverPageProps {
  onSelectMedia: (item: DoubanHotItem) => void;
  onNavigateToLocal?: (folderPath: string) => void;
  visible?: boolean;
  scrollContainerRef?: React.RefObject<HTMLElement | null>;
  defaultSavePath?: string;
}

export default function DiscoverPage({ onSelectMedia, onNavigateToLocal, visible = true, scrollContainerRef, defaultSavePath = "" }: DiscoverPageProps) {
  const state = useDiscoverState({ visible, scrollContainerRef });
  const sub = useDiscoverSubscribe({ activeTabConfig: state.activeTabConfig });

  const {
    primaryTab, setPrimaryTab, activeTab, setActiveTab,
    exploreTab, setExploreTab, exploreRefreshTrigger, setExploreRefreshTrigger,
    exploreRefreshing, setExploreRefreshing,
    subscribeView, setSubscribeView, subscribeFilter, setSubscribeFilter,
    tabDataMap, renderedTabs,
    searchQuery, setSearchQuery, searchItems, searching, isSearchMode,
    doSearch, exitSearch,
    expandedIndex, detail, detailLoading,
    closeExpand, handleCardClick, handleRetry, handleRefreshWithSource,
    refreshing, handleRefresh, loadingMore, loadMore,
    colCount, gridRef, stickyHeaderRef,
    activeTabConfig, displayItems, rowEndIndex,
    searchModalOpen, setSearchModalOpen, searchModalItem, setSearchModalItem, searchModalDetail, setSearchModalDetail,
    openSearchModal, scrollToDiscover, handleRetryTab,
  } = state;

  const {
    subscriptions, refreshSubs, justSubscribed, setJustSubscribed, _isSubscribed,
    isSubscribed, handleSubscribe, handleUnsubscribe, handleSubscribeConfirm,
    subConfigOpen, setSubConfigOpen, subConfigItem, setSubConfigItem, subConfigDetail, setSubConfigDetail,
  } = sub;

  return (
    <div className="mt-8" style={{ minHeight: "100vh" }}>
      <DiscoverHeader
        primaryTab={primaryTab} setPrimaryTab={(tab) => { setPrimaryTab(tab); closeExpand(); setTimeout(() => scrollToDiscover(true), 50); }}
        activeTab={activeTab} setActiveTab={setActiveTab}
        exploreTab={exploreTab} setExploreTab={setExploreTab}
        isSearchMode={isSearchMode} searchQuery={searchQuery} setSearchQuery={setSearchQuery}
        onSearch={doSearch} onExitSearch={exitSearch}
        onRefresh={handleRefresh} refreshing={refreshing}
        scrollToDiscover={scrollToDiscover} stickyHeaderRef={stickyHeaderRef}
        subscribeView={subscribeView} onSetSubscribeView={setSubscribeView}
        subscribeFilter={subscribeFilter} onSetSubscribeFilter={setSubscribeFilter}
        subscribeFilterTabs={[
          { key: "all", label: `全部 (${subscriptions.length})` },
          { key: "active", label: "活跃" },
          { key: "paused", label: "已暂停" },
          { key: "completed", label: "已完成" },
        ]}
        onExploreRefresh={() => setExploreRefreshTrigger(n => n + 1)}
        exploreRefreshing={exploreRefreshing}
      />

      <div style={{ minHeight: "100vh" }}>
        {/* 搜索模式 */}
        {isSearchMode && (
          <div>
            {searching ? (
              <SkeletonGrid colCount={colCount} rows={4} />
            ) : searchItems.length === 0 ? (
              <p className="text-center py-12 text-xs text-slate-600">未找到匹配影片</p>
            ) : (
              <div ref={gridRef} className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-5">
                {searchItems.map((item, index) => (
                  <DiscoverCard key={`search-${item.douban_id || item.title}-${index}`}
                    item={item} index={index} isActive={expandedIndex === index}
                    showRank={false} showMediaType ratingSource="douban" onClick={() => handleCardClick(index)}
                    style={{ order: index <= rowEndIndex || expandedIndex === null ? index : index + 1 }}
                    isSubscribed={justSubscribed.has(`${item.title}|${item.year || ""}`) || _isSubscribed(undefined, item.title, item.year)} />
                ))}
                {expandedIndex !== null && expandedIndex < searchItems.length && (
                  <div key="expand-panel" data-expand-panel
                    className="col-span-full bg-[#141414] border border-white/[0.06] rounded-xl p-5 animate-in fade-in duration-200"
                    style={{ order: rowEndIndex >= 0 ? rowEndIndex + 1 : 9999 }}>
                    <ExpandDetail item={searchItems[expandedIndex]} detail={detail} loading={detailLoading}
                      onSearch={() => openSearchModal(searchItems[expandedIndex], detail)}
                      onClose={closeExpand} onRetry={handleRetry}
                      defaultSource="douban"
                      onRefreshWithSource={handleRefreshWithSource}
                      onNavigateToLocal={onNavigateToLocal}
                      onSubscribe={() => handleSubscribe(searchItems[expandedIndex], detail)}
                      onUnsubscribe={() => handleUnsubscribe(searchItems[expandedIndex])}
                      isSubscribed={isSubscribed(undefined, searchItems[expandedIndex]?.title, searchItems[expandedIndex]?.year)} />
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* 所有已加载的推荐 tab 内容（保持 DOM，用 display:none 隐藏非当前 tab）*/}
        {primaryTab === "recommend" && Array.from(renderedTabs).map(tabKey => (
          <RecommendTabContent key={tabKey} tabKey={tabKey} isActive={tabKey === activeTab}
            isSearchMode={isSearchMode} data={tabDataMap[tabKey] || { items: [], loading: false, error: false, hasMore: true, page: 0 }}
            colCount={colCount} expandedIndex={expandedIndex} detail={detail} detailLoading={detailLoading}
            loadingMore={loadingMore} rowEndIndex={rowEndIndex} gridRef={gridRef}
            onCardClick={handleCardClick} onSelectMedia={(item) => openSearchModal(item, detail)} onCloseExpand={closeExpand}
            onRetry={handleRetry} onRefreshWithSource={handleRefreshWithSource}
            onLoadMore={loadMore} onRetryTab={handleRetryTab}
            onNavigateToLocal={onNavigateToLocal}
            onSubscribe={handleSubscribe}
            onUnsubscribe={handleUnsubscribe}
            checkSubscribed={(item) => justSubscribed.has(`${item.title}|${item.year || ""}`) || _isSubscribed(undefined, item.title, item.year)} />
        ))}

        {/* 探索页 */}
        {primaryTab === "explore" && !isSearchMode && (
          <ExplorePage onSelectMedia={(item) => openSearchModal(item, detail)} activeTab={exploreTab} setActiveTab={setExploreTab}
            colCount={colCount} onNavigateToLocal={onNavigateToLocal}
            onSubscribe={handleSubscribe}
            onUnsubscribe={handleUnsubscribe}
            checkSubscribed={(item) => justSubscribed.has(`${item.title}|${item.year || ""}`) || _isSubscribed(undefined, item.title, item.year)}
            refreshTrigger={exploreRefreshTrigger} onRefreshingChange={setExploreRefreshing} />
        )}

        {/* 订阅页 */}
        {primaryTab === "subscribe" && !isSearchMode && (
          <SubscribeInline subscriptions={subscriptions} onRefresh={() => { refreshSubs(); setJustSubscribed(new Set()); }}
            onOpenSearch={(item) => {
              // 从订阅数据构造搜索弹窗参数，传递清洗名
              const aliases = (item as any).aliases || {};
              const cnName = (aliases.cn?.[0]) || item.title;
              const enName = (aliases.en?.[0]) || "";
              const originalName = (aliases.original?.[0]) || "";
              openSearchModal({
                title: item.title, year: item.year || "", rating: 0,
                cover_url: item.poster || "", subtitle: enName,
                episode: "", douban_id: item.douban_id || "",
                media_type: item.type === "tv" ? "tv" : "movie",
                clean_name_en: enName,
                clean_name_original: originalName,
              } as DoubanHotItem, null);
            }}
            onOpenConfig={(item) => {
              // 打开配置弹窗编辑现有订阅（复用 SubscribeConfigModal）
              setSubConfigItem({
                title: item.title, year: item.year || "", rating: 0,
                cover_url: item.poster || "", subtitle: "",
                episode: "", douban_id: item.douban_id || "",
                media_type: item.type === "tv" ? "tv" : "movie",
              } as DoubanHotItem);
              setSubConfigDetail(null);
              setSubConfigOpen(true);
            }}
            view={subscribeView} filter={subscribeFilter} />
        )}
      </div>

      {/* 搜索资源弹窗 */}
      {searchModalOpen && searchModalItem && (
        <SearchModal
          open={searchModalOpen}
          query={searchModalItem.clean_name_cn || searchModalItem.title}
          onClose={() => { setSearchModalOpen(false); setSearchModalItem(null); setSearchModalDetail(null); }}
          defaultSavePath={defaultSavePath}
          cnName={searchModalItem.clean_name_cn || searchModalItem.title}
          enName={searchModalDetail?.english_title || searchModalItem.clean_name_en || (searchModalItem as any)._tmdb_original_title || searchModalDetail?.original_title || searchModalItem.subtitle || ""}
          originalName={searchModalItem.clean_name_original || searchModalDetail?.original_title || ""}
          mediaType={searchModalItem.media_type || activeTabConfig.mediaType || "movie"}
          seasonNumber={searchModalItem.episode ? parseInt(searchModalItem.episode) || 0 : 0}
        />
      )}

      {/* 订阅配置弹窗 */}
      <SubscribeConfigModal
        open={subConfigOpen}
        onClose={() => { setSubConfigOpen(false); setSubConfigItem(null); setSubConfigDetail(null); }}
        onConfirm={handleSubscribeConfirm}
        title={subConfigItem?.title || ""}
        mediaType={subConfigItem?.media_type || activeTabConfig.mediaType === "tv" ? "tv" : "movie"}
        defaultSavePath={defaultSavePath}
      />
    </div>
  );
}
