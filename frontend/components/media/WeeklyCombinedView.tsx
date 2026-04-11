// 发现页周榜合并视图（华语+全球上下排列带排名 + 内嵌展开面板）
"use client";
import { useRef, useCallback } from "react";
import type { DoubanHotItem } from "@/types";
import type { MediaDetail } from "./discoverUtils";
import DiscoverCard from "./DiscoverCard";
import ExpandDetail from "./ExpandDetail";

export interface WeeklyCombinedViewProps {
  chineseItems: DoubanHotItem[];
  globalItems: DoubanHotItem[];
  expandedIndex: number | null;
  onCardClick: (index: number) => void;
  detail: MediaDetail | null;
  detailLoading: boolean;
  onSearch: (item: DoubanHotItem) => void;
  onCloseExpand: () => void;
  onRetry: () => void;
}

export default function WeeklyCombinedView({
  chineseItems, globalItems, expandedIndex, onCardClick,
  detail, detailLoading, onSearch, onCloseExpand, onRetry,
}: WeeklyCombinedViewProps) {
  return (
    <div>
      <RankSection title="华语口碑剧集周榜" items={chineseItems} indexOffset={0}
        expandedIndex={expandedIndex} onCardClick={onCardClick}
        detail={detail} detailLoading={detailLoading}
        onSearch={onSearch} onCloseExpand={onCloseExpand} onRetry={onRetry} />
      <RankSection title="全球口碑剧集周榜" items={globalItems} indexOffset={chineseItems.length}
        expandedIndex={expandedIndex} onCardClick={onCardClick}
        detail={detail} detailLoading={detailLoading}
        onSearch={onSearch} onCloseExpand={onCloseExpand} onRetry={onRetry} />
    </div>
  );
}

function RankSection({ title, items, indexOffset, expandedIndex, onCardClick, detail, detailLoading, onSearch, onCloseExpand, onRetry }: {
  title: string; items: DoubanHotItem[]; indexOffset: number;
  expandedIndex: number | null; onCardClick: (index: number) => void;
  detail: MediaDetail | null; detailLoading: boolean;
  onSearch: (item: DoubanHotItem) => void; onCloseExpand: () => void; onRetry: () => void;
}) {
  const gridRef = useRef<HTMLDivElement>(null);

  const getRowEndIndex = useCallback((clickIndex: number): number => {
    if (!gridRef.current) return clickIndex;
    const cards = gridRef.current.querySelectorAll<HTMLElement>("[data-discover-card]");
    const localIdx = clickIndex - indexOffset;
    if (!cards[localIdx]) return clickIndex;
    const clickTop = cards[localIdx].offsetTop;
    let lastLocal = localIdx;
    for (let i = localIdx + 1; i < cards.length; i++) {
      if (cards[i].offsetTop === clickTop) lastLocal = i; else break;
    }
    return lastLocal;
  }, [indexOffset]);

  // 当前 section 内是否有展开的卡片
  const localExpanded = expandedIndex !== null && expandedIndex >= indexOffset && expandedIndex < indexOffset + items.length;
  const localExpandIdx = localExpanded ? expandedIndex! - indexOffset : -1;
  const rowEnd = localExpanded ? getRowEndIndex(expandedIndex!) : -1;

  return (
    <div>
      <div className="mt-5 mb-3">
        <span className="text-[13px] font-medium text-slate-300">{title}</span>
      </div>
      <div ref={gridRef} className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-5">
        {items.map((item, i) => (
          <DiscoverCard key={`${item.douban_id || i}`}
            item={item} index={i} isActive={expandedIndex === i + indexOffset}
            showRank ratingSource="douban"
            onClick={() => onCardClick(i + indexOffset)}
            style={{ order: localExpanded ? (i <= rowEnd ? i : i + 1) : i }} />
        ))}
        {localExpanded && localExpandIdx >= 0 && localExpandIdx < items.length && (
          <div key="expand-panel" data-expand-panel
            className="col-span-full bg-[#141414] border border-white/[0.06] rounded-xl p-5 animate-in fade-in duration-200"
            style={{ order: rowEnd >= 0 ? rowEnd + 1 : 9999 }}>
            <ExpandDetail item={items[localExpandIdx]} detail={detail} loading={detailLoading}
              onSearch={() => onSearch({...items[localExpandIdx], _tmdb_original_title: detail?.original_title || ""} as any)}
              onClose={onCloseExpand} onRetry={onRetry}
              defaultSource="douban" />
          </div>
        )}
      </div>
    </div>
  );
}
