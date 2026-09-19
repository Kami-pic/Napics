// 移动端搜索：包裹共享搜索状态机，适配路由页。不复制第二套状态机。
//
// URL 是唯一的搜索触发源：提交新词只改 URL，由 query effect 发搜索。
// 同词重试才直接调搜索函数 —— 否则「改 URL」和「直接搜」会各搜一次。
"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { useSearchState } from "@/components/search/useSearchState";
import { useMobileConfig } from "@/components/mobile/MobileProviders";
import { resourceSearchUrl, type MobileSearchQuery, type MobileSearchTab } from "@/lib/mobile/mobileRouteUtils";

export interface MobileSearchController {
  /** 共享搜索状态机的全部返回值 */
  search: ReturnType<typeof useSearchState>;
  /** 搜索框里的草稿词（未提交） */
  draft: string;
  setDraft: (value: string) => void;
  /** 提交搜索：只改 URL */
  submit: () => void;
  /**
   * 用指定词重搜（历史词 / 回退词点击）。plain=true 时**丢掉结构化上下文**
   * （季号、中英文名、folderType），只用这个纯关键词搜 —— 这样"删掉第三季"
   * 才真的生效，否则后端会拿残留的季号上下文继续构造带季号的默认词。
   */
  submitKeyword: (keyword: string, opts?: { plain?: boolean }) => void;
  /** 同词重试：URL 不变，直接重搜 */
  retry: () => void;
  switchTab: (tab: MobileSearchTab) => void;
  tab: MobileSearchTab;
}

export function useMobileSearch(query: MobileSearchQuery): MobileSearchController {
  const router = useRouter();
  const { defaultSavePath } = useMobileConfig();
  const [draft, setDraft] = useState(query.q);
  const [syncedQuery, setSyncedQuery] = useState(query.q);

  // URL 里的词变了就同步草稿（从媒体详情跳进来、或用户按了返回）。
  // 用渲染期调整 state 而不是 effect：effect 里 setState 会多一次渲染，
  // 而这个值是纯派生的。
  if (query.q !== syncedQuery) {
    setSyncedQuery(query.q);
    setDraft(query.q);
  }

  const search = useSearchState({
    open: true,
    query: query.q,
    // 媒体详情带过来的保存目录优先，其次是 Config 的默认扫描路径
    defaultSavePath: query.savePath || defaultSavePath,
    currentResolution: query.resolution,
    mediaType: query.mediaType,
    cnName: query.cnName,
    enName: query.enName,
    originalName: query.originalName,
    folderType: query.folderType,
    seasonNumber: query.season,
  });

  // 网盘 Tab 的搜索不由 useSearchState 自动触发，这里补上。
  // doPanSearch 内部有缓存，同词重复调用不会重复请求。
  const lastPanKeyRef = useRef("");
  useEffect(() => {
    if (query.tab !== "pan" || !query.q) return;
    const key = `${query.q}|${query.mediaType ?? ""}`;
    if (lastPanKeyRef.current === key) return;
    lastPanKeyRef.current = key;
    void search.doPanSearch(query.q);
  }, [query.tab, query.q, query.mediaType, search]);

  const submit = useCallback(() => {
    const next = draft.trim();
    if (!next) return;
    // 只改 URL。query effect 会发搜索，这里不能再调一次 doSearch，否则双搜
    router.replace(resourceSearchUrl({ ...query, q: next }));
  }, [draft, query, router]);

  const submitKeyword = useCallback((keyword: string, opts?: { plain?: boolean }) => {
    const next = keyword.trim();
    if (!next) return;
    setDraft(next);
    if (opts?.plain) {
      // 丢掉结构化上下文，只保留 tab / 保存路径 —— 让纯关键词真正生效
      router.replace(resourceSearchUrl({ q: next, tab: query.tab, savePath: query.savePath }));
    } else {
      router.replace(resourceSearchUrl({ ...query, q: next }));
    }
  }, [query, router]);

  const retry = useCallback(() => {
    if (!query.q) return;
    // 同词重试：URL 不会变，effect 不会重跑，只能直接调
    if (query.tab === "pan") void search.doPanSearch(query.q);
    else void search.doSearch(query.q);
  }, [query.q, query.tab, search]);

  const switchTab = useCallback((tab: MobileSearchTab) => {
    search.setActiveTab(tab);
    router.replace(resourceSearchUrl({ ...query, tab }));
  }, [query, router, search]);

  return { search, draft, setDraft, submit, submitKeyword, retry, switchTab, tab: query.tab };
}
