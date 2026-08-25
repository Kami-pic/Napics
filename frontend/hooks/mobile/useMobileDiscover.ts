// 移动端发现榜单的数据入口：每个 tab 一份独立缓存 + offset 分页。
//
// 两条硬约束：
// 1. **分页量固定**（MOBILE_DISCOVER_PAGE_SIZE），不跟视口列数联动。桌面 useDiscoverState
//    把请求量绑在列数上，横竖屏切换就得清缓存重拉；这里连列数都不读，转屏天然无副作用。
// 2. **hasMore 只能靠"本页条数 < 请求条数"判**。后端返回的 count 是本页条数不是总数
//    （只有 combined 命中文件缓存时才是全量长度），没有可靠的总数字段。
"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { DoubanHotItem } from "@/types";
import { api } from "@/lib/api";
import { RECOMMEND_TABS, normalizeItem, type RecommendSource } from "@/components/media/discoverUtils";
import { MOBILE_DISCOVER_PAGE_SIZE } from "@/lib/mobile/mobileConstants";
import type { MobileViewState } from "@/components/mobile/MobileStateView";

/** 前端合成的伪 tab：后端没有"周榜"这个源，要并发拉华语榜 + 全球榜再拼 */
const WEEKLY_TAB = "weekly_combined";
const WEEKLY_SOURCES = ["douban_weekly_chinese", "douban_weekly_global"] as const;

const LOAD_FAILED_TEXT = "榜单加载失败，检查后端与网络是否正常";

interface TabState {
  items: DoubanHotItem[];
  /** 已加载到第几页（0 起） */
  page: number;
  hasMore: boolean;
  loading: boolean;
  loadingMore: boolean;
  /** 首屏失败。追加失败走 moreFailed，不清掉已有内容 */
  failed: boolean;
  moreFailed: boolean;
}

const EMPTY_TAB: TabState = {
  items: [], page: 0, hasMore: false, loading: false, loadingMore: false, failed: false, moreFailed: false,
};

/** 去重键：豆瓣/TMDB id 优先，没有 id 的源退回片名 */
function itemKey(item: DoubanHotItem): string {
  return item.douban_id || item.title;
}

async function fetchPage(tabKey: string, page: number): Promise<{ items: DoubanHotItem[]; hasMore: boolean }> {
  if (tabKey === WEEKLY_TAB) {
    const parts = await Promise.all(
      WEEKLY_SOURCES.map(src => api.discoverRecommend(src, 0, MOBILE_DISCOVER_PAGE_SIZE)),
    );
    const items = parts.flatMap(p => (p.items || []) as unknown[]).map(normalizeItem);
    // 周榜是固定榜单，两个源各自就那么多条，没有下一页
    return { items, hasMore: false };
  }
  const data = await api.discoverRecommend(tabKey, page * MOBILE_DISCOVER_PAGE_SIZE, MOBILE_DISCOVER_PAGE_SIZE);
  const items = ((data.items || []) as unknown[]).map(normalizeItem);
  return { items, hasMore: items.length >= MOBILE_DISCOVER_PAGE_SIZE };
}

export interface UseMobileDiscoverResult {
  tabs: RecommendSource[];
  activeTab: string;
  activeTabConfig: RecommendSource;
  setActiveTab: (tab: string) => void;
  items: DoubanHotItem[];
  state: MobileViewState;
  errorText: string;
  hasMore: boolean;
  loadingMore: boolean;
  moreFailed: boolean;
  loadMore: () => void;
  retry: () => void;
}

/**
 * @param enabled 插件可用性还没查完、或没装 feature-discover 时传 false。
 *   门控必须在 hook 里：放在组件里"提前 return"是拦不住的，effect 早就发出去了。
 */
export function useMobileDiscover(initialTab?: string, enabled = true): UseMobileDiscoverResult {
  const tabs = RECOMMEND_TABS;
  const [activeTab, setActiveTab] = useState<string>(
    () => tabs.find(t => t.key === initialTab)?.key || tabs[0].key,
  );
  const [tabMap, setTabMap] = useState<Record<string, TabState>>({});

  // 已提交的 tabMap 快照，供 effect 与回调读取（不进依赖数组，避免每次数据变化都重建回调）
  const tabMapRef = useRef<Record<string, TabState>>({});
  useEffect(() => { tabMapRef.current = tabMap; }, [tabMap]);

  // 每个 tab 一个自增号，只认最后一次发起的请求。共用一个号会让并发的两个 tab 互相取消
  const genRef = useRef<Record<string, number>>({});

  const loadTab = useCallback(async (tabKey: string, page: number, append: boolean) => {
    const gen = (genRef.current[tabKey] ?? 0) + 1;
    genRef.current[tabKey] = gen;

    // 让"标记 loading"落在 effect 的同步阶段之外：进页面时在 effect 里直接 setState
    // 会多一次级联渲染（React 19 的 set-state-in-effect 就是在拦这个）。
    await Promise.resolve();

    setTabMap(prev => ({
      ...prev,
      [tabKey]: {
        ...(prev[tabKey] || EMPTY_TAB),
        loading: !append,
        loadingMore: append,
        failed: false,
        moreFailed: false,
      },
    }));

    try {
      const { items, hasMore } = await fetchPage(tabKey, page);
      if (genRef.current[tabKey] !== gen) return;
      setTabMap(prev => {
        const old = prev[tabKey] || EMPTY_TAB;
        const base = append ? old.items : [];
        const seen = new Set(base.map(itemKey));
        const merged = [...base];
        for (const it of items) {
          const key = itemKey(it);
          if (seen.has(key)) continue;
          seen.add(key);
          merged.push(it);
        }
        // 追加时一条新的都没有 → 后端在原地打转，别再让用户点下一页
        const grew = merged.length > base.length;
        return {
          ...prev,
          [tabKey]: {
            items: merged,
            page,
            hasMore: hasMore && (!append || grew),
            loading: false,
            loadingMore: false,
            failed: false,
            moreFailed: false,
          },
        };
      });
    } catch {
      if (genRef.current[tabKey] !== gen) return;
      setTabMap(prev => {
        const old = prev[tabKey] || EMPTY_TAB;
        return {
          ...prev,
          [tabKey]: {
            ...old,
            loading: false,
            loadingMore: false,
            // 追加失败不清空已看到的内容，只在"加载更多"处提示可重试
            failed: append ? old.failed : true,
            moreFailed: append,
          },
        };
      });
    }
  }, []);

  // 切到没加载过的 tab 才发请求；切回来看过的 tab 直接用缓存
  useEffect(() => {
    if (!enabled) return;
    if (tabMapRef.current[activeTab]) return;
    // loadTab 内的 setState 全在 await 之后（进页面不会级联渲染），但 set-state-in-effect
    // 规则穿不透 async callback，只能显式豁免。
    // eslint-disable-next-line react-hooks/set-state-in-effect -- setState 都发生在 await 之后
    void loadTab(activeTab, 0, false);
  }, [activeTab, loadTab, enabled]);

  const cur = tabMap[activeTab] || EMPTY_TAB;
  const hasEntry = Boolean(tabMap[activeTab]);

  const loadMore = useCallback(() => {
    const now = tabMapRef.current[activeTab] || EMPTY_TAB;
    if (now.loading || now.loadingMore) return;
    void loadTab(activeTab, now.page + 1, true);
  }, [activeTab, loadTab]);

  const retry = useCallback(() => {
    void loadTab(activeTab, 0, false);
  }, [activeTab, loadTab]);

  const activeTabConfig = useMemo(
    () => tabs.find(t => t.key === activeTab) || tabs[0],
    [tabs, activeTab],
  );

  let state: MobileViewState = "ready";
  if (cur.failed) state = "error";
  else if (!hasEntry || cur.loading) state = "loading";
  else if (cur.items.length === 0) state = "empty";

  return {
    tabs,
    activeTab,
    activeTabConfig,
    setActiveTab,
    items: cur.items,
    state,
    errorText: LOAD_FAILED_TEXT,
    hasMore: cur.hasMore,
    loadingMore: cur.loadingMore,
    moreFailed: cur.moreFailed,
    loadMore,
    retry,
  };
}
