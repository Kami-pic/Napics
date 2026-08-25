// 发现榜单的两列网格 + "加载更多"。
//
// 手动点按而不是滚动到底自动加载：自动加载会让页面高度一直变，
// 从详情返回时滚动位置对不上，而且没网时会静默什么都不发生。
"use client";
import type { DoubanHotItem } from "@/types";
import { MOBILE_GRID_COLUMNS } from "@/lib/mobile/mobileConstants";
import MobileDiscoverCard from "./MobileDiscoverCard";

export interface MobileDiscoverGridProps {
  items: DoubanHotItem[];
  showRank?: boolean;
  showMediaType?: boolean;
  hasMore: boolean;
  loadingMore: boolean;
  /** 追加失败：已有内容留着，只在这里说一句可重试 */
  moreFailed: boolean;
  onOpen: (item: DoubanHotItem) => void;
  onLoadMore: () => void;
}

export default function MobileDiscoverGrid({
  items, showRank, showMediaType, hasMore, loadingMore, moreFailed, onOpen, onLoadMore,
}: MobileDiscoverGridProps) {
  return (
    <div className="flex flex-col gap-3">
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: `repeat(${MOBILE_GRID_COLUMNS}, minmax(0, 1fr))` }}
      >
        {items.map((item, index) => (
          <MobileDiscoverCard
            key={`${item.douban_id || item.title}-${index}`}
            item={item}
            index={index}
            showRank={showRank}
            showMediaType={showMediaType}
            onOpen={onOpen}
          />
        ))}
      </div>

      {moreFailed && (
        <p className="text-center text-[12px] text-[var(--m-danger)]" role="alert">
          加载更多失败，点下面的按钮再试一次
        </p>
      )}

      {hasMore && (
        <button
          type="button"
          onClick={onLoadMore}
          disabled={loadingMore}
          className="mx-auto w-full rounded-[var(--m-radius)] text-[14px] text-[var(--m-text)] disabled:opacity-60"
          style={{
            minHeight: "var(--m-touch-min)",
            background: "var(--m-surface)",
            border: "1px solid var(--m-border)",
          }}
        >
          {loadingMore ? "加载中…" : "加载更多"}
        </button>
      )}
    </div>
  );
}
