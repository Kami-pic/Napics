// 发现首页（/m）。榜单占满整屏 —— 底栏已经有媒体库/搜索/下载三个 Tab，
// 首页再放同样的入口卡是交互冲突。
//
// 卡片点击进"发现详情"，不直接跳搜索：和媒体库详情一个口径，先看信息再决定搜不搜。
"use client";
import { useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type { DoubanHotItem } from "@/types";
import { useMobileDiscover } from "@/hooks/mobile/useMobileDiscover";
import { discoverDetailUrl, discoverUrl, MOBILE_ROUTES } from "@/lib/mobile/mobileRouteUtils";
import { useMobilePlugins } from "./MobileProviders";
import MobileStateView from "./MobileStateView";
import MobileDiscoverTabs from "./MobileDiscoverTabs";
import MobileDiscoverGrid from "./MobileDiscoverGrid";

export interface MobileDiscoverClientProps {
  /** 来自 URL 的榜单 tab，为空时用第一个 */
  initialTab?: string;
}

export default function MobileDiscoverClient({ initialTab }: MobileDiscoverClientProps) {
  const router = useRouter();
  const { hasDiscover, ready: pluginsReady } = useMobilePlugins();
  const {
    tabs, activeTab, activeTabConfig, setActiveTab,
    items, state, errorText, hasMore, loadingMore, moreFailed, loadMore, retry,
  } = useMobileDiscover(initialTab, pluginsReady && hasDiscover);

  // tab 写进 URL 才能"从哪进回哪里"；用 replace，否则每切一次 tab 都往历史栈压一层
  const onChangeTab = useCallback((tab: string) => {
    setActiveTab(tab);
    router.replace(discoverUrl(tab));
  }, [setActiveTab, router]);

  const onOpen = useCallback((item: DoubanHotItem) => {
    router.push(discoverDetailUrl({
      title: item.title,
      year: item.year,
      // 条目自己带类型就用它；混合榜单里 tab 的 mediaType 是 mixed，不能当类型用
      mediaType: item.media_type || (activeTabConfig.mediaType === "tv" ? "tv" : "movie"),
      source: activeTabConfig.ratingSource,
      id: item.douban_id,
      subtitle: item.subtitle,
      cnName: item.clean_name_cn,
      enName: item.clean_name_en,
      originalName: item.clean_name_original,
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
            href={MOBILE_ROUTES.search}
            className="flex items-center rounded-[var(--m-radius-sm)] px-4 text-sm text-[var(--m-text)]"
            style={{ minHeight: "var(--m-touch-min)", background: "var(--m-surface-raised)" }}
          >
            直接去搜索
          </Link>
        }
      />
    );
  }

  return (
    <div className="flex flex-col">
      <MobileDiscoverTabs tabs={tabs} activeTab={activeTab} onChange={onChangeTab} />
      <MobileStateView
        state={pluginsReady ? state : "loading"}
        loadingText="正在加载榜单…"
        errorText={errorText}
        emptyText="这个榜单暂时没有内容，换一个试试"
        onRetry={retry}
      >
        <MobileDiscoverGrid
          items={items}
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
  );
}
