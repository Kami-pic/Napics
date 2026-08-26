// 发现榜单的两列网格 + "加载更多"。
//
// 手动点按而不是滚动到底自动加载：自动加载会让页面高度一直变，没网时还会静默
// 什么都不发生（用户只看到滚到底没反应）。
//
// 已知取舍：榜单缓存是页面组件内的 state，从详情返回时组件重建，翻过的页会回到第一页。
// 要跨路由段保住，得把 {tab: {items, page}} 提到 Provider 或 sessionStorage 里。
//
// 支持分段（周榜是华语 + 全球两个榜拼的）：排名必须在**段内**从 1 开始数，
// 首尾相接后用全局下标会把全球榜第 1 名标成第 21 名。
"use client";
import type { DoubanHotItem } from "@/types";
import type { MobileDiscoverGroup } from "@/hooks/mobile/useMobileDiscover";
import { MOBILE_GRID_COLUMNS } from "@/lib/mobile/mobileConstants";
import MobileDiscoverCard from "./MobileDiscoverCard";

export interface MobileDiscoverGridProps {
  items: DoubanHotItem[];
  /** 有分段时按段渲染，忽略 items（items 仍用于空态判断） */
  groups?: MobileDiscoverGroup[] | null;
  showRank?: boolean;
  showMediaType?: boolean;
  hasMore: boolean;
  loadingMore: boolean;
  /** 追加失败：已有内容留着，只在这里说一句可重试 */
  moreFailed: boolean;
  onOpen: (item: DoubanHotItem) => void;
  onLoadMore: () => void;
}

function CardGrid({
  items, showRank, showMediaType, onOpen,
}: Pick<MobileDiscoverGridProps, "items" | "showRank" | "showMediaType" | "onOpen">) {
  return (
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
  );
}

export default function MobileDiscoverGrid({
  items, groups, showRank, showMediaType, hasMore, loadingMore, moreFailed, onOpen, onLoadMore,
}: MobileDiscoverGridProps) {
  return (
    <div className="flex flex-col gap-3">
      {groups && groups.length > 0 ? (
        groups.map(group => (
          <section key={group.label} className="flex flex-col gap-2">
            <h2 className="text-[13px] font-medium text-[var(--m-text-muted)]">{group.label}</h2>
            <CardGrid
              items={group.items}
              showRank={showRank}
              showMediaType={showMediaType}
              onOpen={onOpen}
            />
          </section>
        ))
      ) : (
        <CardGrid items={items} showRank={showRank} showMediaType={showMediaType} onOpen={onOpen} />
      )}

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
