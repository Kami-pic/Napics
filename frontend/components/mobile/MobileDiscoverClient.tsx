// 发现首页（/m）。榜单占满整屏 —— 底栏已经有媒体库/搜索/下载三个 Tab，
// 首页再放同样的入口卡是交互冲突。
//
// 卡片点击进"发现详情"，不直接跳搜索：和媒体库详情一个口径，先看信息再决定搜不搜。
"use client";
import { useCallback, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type { DoubanHotItem } from "@/types";
import { useMobileDiscover } from "@/hooks/mobile/useMobileDiscover";
import { discoverDetailUrl, discoverUrl, MOBILE_ROUTES } from "@/lib/mobile/mobileRouteUtils";
import { useMobilePlugins } from "./MobileProviders";
import MobileStateView from "./MobileStateView";
import MobileChipRow from "./MobileChipRow";
import MobileDiscoverGrid from "./MobileDiscoverGrid";

/** tablist ↔ tabpanel 的关联 id。页面上只有一组榜单，写成常量即可 */
const PANEL_ID = "m-discover-panel";

export interface MobileDiscoverClientProps {
  /** 来自 URL 的榜单 tab，为空时用第一个 */
  initialTab?: string;
}

export default function MobileDiscoverClient({ initialTab }: MobileDiscoverClientProps) {
  const router = useRouter();
  const { hasDiscover, ready: pluginsReady } = useMobilePlugins();
  const {
    tabs, activeTab, activeTabConfig, setActiveTab,
    items, groups, state, errorText, hasMore, loadingMore, moreFailed, loadMore, retry,
  } = useMobileDiscover(initialTab, pluginsReady && hasDiscover);

  // tab 写进 URL 才能"从哪进回哪里"；用 replace，否则每切一次 tab 都往历史栈压一层
  const onChangeTab = useCallback((tab: string) => {
    setActiveTab(tab);
    router.replace(discoverUrl(tab));
  }, [setActiveTab, router]);

  const chips = useMemo(
    () => tabs.map(tab => ({ key: tab.key, label: tab.label })),
    [tabs],
  );

  const onOpen = useCallback((item: DoubanHotItem) => {
    router.push(discoverDetailUrl({
      title: item.title,
      year: item.year,
      // 条目自己带类型就用它；混合榜单里 tab 的 mediaType 是 mixed，不能当类型用
      mediaType: item.media_type || (activeTabConfig.mediaType === "tv" ? "tv" : "movie"),
      source: activeTabConfig.ratingSource,
      // 综合推荐是混合来源：条目可能来自 TMDB 或 Bangumi，而这个 tab 的 ratingSource
      // 固定是 douban，且 normalizeItem 会把缺失的 douban_id 回退成 tmdb_id 字符串。
      // 把这种 id 当豆瓣 id 直查会命中**另一部片子**并写进详情缓存，
      // 所以综合榜不传 id，让后端按片名 + 年份匹配。
      // （桌面 useDiscoverState 有同样的错配，本轮不动桌面。）
      id: activeTab === "combined" ? undefined : item.douban_id,
      subtitle: item.subtitle,
      cnName: item.clean_name_cn,
      enName: item.clean_name_en,
      originalName: item.clean_name_original,
      // 卡片上的海报直接带过去，详情页第一帧就有图（/media/info 冷缓存要 6 秒）
      cover: item.cover_url,
      localStatus: item.local_status,
      localFolder: item.local_folder,
      tab: activeTab,
    }));
  }, [router, activeTab, activeTabConfig]);

  // 插件不可用：给出口，不留一句"不可用"就结束
  if (pluginsReady && !hasDiscover) {
    return (
      <MobileStateView
        state="empty"
        emptyText="没有安装发现插件（feature-discover），榜单推荐不可用"
        emptyAction={
          <Link
            href={MOBILE_ROUTES.resource}
            className="flex items-center rounded-[var(--m-radius-sm)] px-4 text-sm text-[var(--m-text)]"
            style={{ minHeight: "var(--m-touch-min)", background: "var(--m-surface-raised)" }}
          >
            直接搜资源
          </Link>
        }
      />
    );
  }

  return (
    <div className="flex flex-col gap-2 py-2">
      <MobileChipRow
        items={chips}
        activeKey={activeTab}
        onChange={onChangeTab}
        ariaLabel="榜单"
        semantics="tab"
        controlsId={PANEL_ID}
      />
      {/* tabpanel 与上面的 tablist 配对，读屏才能说出"这块内容属于哪个榜单" */}
      <div id={PANEL_ID} role="tabpanel" aria-label={activeTabConfig.label}>
        <MobileStateView
          state={pluginsReady ? state : "loading"}
          loadingText="正在加载榜单…"
          errorText={errorText}
          emptyText="这个榜单暂时没有内容，换一个试试"
          onRetry={retry}
        >
          <MobileDiscoverGrid
            items={items}
            groups={groups}
            showRank={activeTabConfig.showRank}
            showMediaType={activeTabConfig.mediaType === "mixed"}
            hasMore={hasMore}
            loadingMore={loadingMore}
            moreFailed={moreFailed}
            onOpen={onOpen}
            onLoadMore={loadMore}
          />
        </MobileStateView>
      </div>
    </div>
  );
}
