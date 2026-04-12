// 推荐 tab 内容面板（单个 tab 的卡片网格+展开面板+滚动自动加载）
"use client";
import { useRef, useEffect, useCallback, useState } from "react";
import type { DoubanHotItem } from "@/types";
import type { MediaDetail, RecommendSource } from "./discoverUtils";
import { RECOMMEND_TABS } from "./discoverUtils";
import DiscoverCard from "./DiscoverCard";
import SkeletonGrid from "./SkeletonGrid";
import ExpandDetail from "./ExpandDetail";
import WeeklyCombinedView from "./WeeklyCombinedView";

interface TabState {
  items: DoubanHotItem[];
  loading: boolean;
  error: boolean;
  hasMore: boolean;
  page: number;
  weeklyChineseItems?: DoubanHotItem[];
  weeklyGlobalItems?: DoubanHotItem[];
}

// 前 4 批滚动自动加载，之后手动点击
const AUTO_LOAD_BATCHES = 4;
// 总上限
const MAX_ITEMS = 200;

export interface RecommendTabContentProps {
  tabKey: string;
  isActive: boolean;
  isSearchMode: boolean;
  data: TabState;
  colCount: number;
  expandedIndex: number | null;
  detail: MediaDetail | null;
  detailLoading: boolean;
  loadingMore: boolean;
  rowEndIndex: number;
  gridRef: React.RefObject<HTMLDivElement | null>;
  onCardClick: (index: number) => void;
  onSelectMedia: (item: DoubanHotItem) => void;
  onCloseExpand: () => void;
  onRetry: () => void;
  onRefreshWithSource: (source: string) => void;
  onLoadMore: () => void;
  onRetryTab: (tabKey: string) => void;
}

export default function RecommendTabContent({
  tabKey, isActive, isSearchMode, data, colCount,
  expandedIndex, detail, detailLoading, loadingMore, rowEndIndex, gridRef,
  onCardClick, onSelectMedia, onCloseExpand, onRetry, onRefreshWithSource, onLoadMore, onRetryTab,
}: RecommendTabContentProps) {
  const tabConfig = RECOMMEND_TABS.find(t => t.key === tabKey) || RECOMMEND_TABS[0];
  const isWeekly = tabKey === "weekly_combined";
  const isCombined = tabKey === "combined";
  const tabItems = data.items;
  const sentinelRef = useRef<HTMLDivElement>(null);
  const [autoLoadPending, setAutoLoadPending] = useState(false);
  const loadingRef = useRef(false);

  // 综合推荐上限 60，其他 200
  const itemMax = isCombined ? 60 : MAX_ITEMS;
  const batchCount = data.page + 1;
  const isAutoMode = batchCount < AUTO_LOAD_BATCHES;
  const reachedMax = tabItems.length >= itemMax;
  // 综合推荐和周榜显示排名
  const showRank = !!tabConfig.showRank || isCombined;

  // 同步 loading 状态到 ref
  loadingRef.current = loadingMore || autoLoadPending;

  // IntersectionObserver 自动加载
  useEffect(() => {
    if (!isActive || !isAutoMode || !data.hasMore || loadingMore || data.loading || isWeekly || reachedMax) return;
    if (!sentinelRef.current) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !loadingRef.current) {
        loadingRef.current = true;
        setAutoLoadPending(true);
        setTimeout(() => {
          onLoadMore();
          setAutoLoadPending(false);
        }, 400);
      }
    }, { threshold: 0.1 });
    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [isActive, isAutoMode, data.hasMore, loadingMore, data.loading, isWeekly, reachedMax, onLoadMore]);

  return (
    <div key={tabKey} style={{ display: isActive && !isSearchMode ? undefined : "none" }}>
      {data.loading && (isWeekly ? !(data.weeklyChineseItems?.length) : tabItems.length === 0) ? (
        <SkeletonGrid colCount={colCount} rows={4} />
      ) : data.error ? (
        <div className="text-center py-12">
          <p className="text-xs text-slate-600 mb-2">加载失败</p>
          <button onClick={() => onRetryTab(tabKey)} className="text-xs text-blue-400 hover:text-blue-300">重试</button>
        </div>
      ) : isWeekly ? (
        <WeeklyCombinedView
          chineseItems={data.weeklyChineseItems || []} globalItems={data.weeklyGlobalItems || []}
          expandedIndex={isActive ? expandedIndex : null} onCardClick={onCardClick}
          detail={detail} detailLoading={detailLoading}
          onSearch={(item) => onSelectMedia({...item, _tmdb_original_title: detail?.original_title || ""} as any)}
          onCloseExpand={onCloseExpand} onRetry={onRetry}
        />
      ) : tabItems.length === 0 ? (
        <p className="text-center py-12 text-xs text-slate-600">暂无数据</p>
      ) : (
        <>
          <div ref={isActive ? gridRef : undefined}
            className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-5">
            {tabItems.map((item, index) => (
              <DiscoverCard key={`card-${tabKey}-${item.douban_id || item.title}-${index}`}
                item={item} index={index} isActive={isActive && expandedIndex === index}
                showRank={showRank}
                showMediaType={tabConfig.mediaType === "mixed"}
                ratingSource={tabConfig.ratingSource || "douban"}
                onClick={() => onCardClick(index)}
                style={isActive ? { order: index <= rowEndIndex || expandedIndex === null ? index : index + 1 } : undefined} />
            ))}
            {isActive && expandedIndex !== null && expandedIndex < tabItems.length && (
              <div key="expand-panel" data-expand-panel
                className="col-span-full bg-[#141414] border border-white/[0.06] rounded-xl p-5 animate-in fade-in duration-200"
                style={{ order: rowEndIndex >= 0 ? rowEndIndex + 1 : 9999 }}>
                <ExpandDetail item={tabItems[expandedIndex]} detail={detail} loading={detailLoading}
                  onSearch={() => onSelectMedia({...tabItems[expandedIndex], _tmdb_original_title: detail?.original_title || ""} as any)}
                  onClose={onCloseExpand} onRetry={onRetry}
                  defaultSource={tabConfig.ratingSource || "douban"}
                  showBangumiRating={tabConfig.ratingSource === "bangumi" || tabKey === "douban_animation"}
                  onRefreshWithSource={onRefreshWithSource} />
              </div>
            )}
          </div>

          {/* 底部加载区域 */}
          {isActive && !reachedMax && data.hasMore && (
            <>
              {/* 自动加载模式：哨兵元素 + 骨骼行 */}
              {isAutoMode ? (
                <div ref={sentinelRef} className="mt-5">
                  {(loadingMore || autoLoadPending) && <SkeletonGrid colCount={colCount} rows={1} />}
                </div>
              ) : (
                /* 手动加载模式：点击按钮 */
                <div className="flex justify-center mt-6 pb-8">
                  <button onClick={onLoadMore} disabled={loadingMore}
                    className="px-5 py-2 text-xs text-slate-400 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06] rounded-lg transition-all disabled:opacity-50">
                    {loadingMore ? "加载中..." : "查看更多"}
                  </button>
                </div>
              )}
            </>
          )}
          {isActive && reachedMax && (
            <p className="text-center py-6 text-xs text-slate-600">
              {isCombined ? "今天就推荐这么多吧" : "已加载全部"}
            </p>
          )}
          {isActive && !data.hasMore && !reachedMax && tabItems.length > 0 && (
            <p className="text-center py-6 text-xs text-slate-600">
              {isCombined ? "今天就推荐这么多吧" : "已加载全部"}
            </p>
          )}
        </>
      )}
    </div>
  );
}
