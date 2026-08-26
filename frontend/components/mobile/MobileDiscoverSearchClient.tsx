// 底栏「搜索」= 按片名找片子（豆瓣搜索）。
//
// 这里**不是**资源搜索。用户日常想的"搜索"是"这部片有没有、评分多少、本地有没有"，
// 而不是"哪个种子画质好"—— 后者需要先有一个明确的目标，入口在详情页的「搜索资源」。
//
// URL 是唯一状态源：提交只改 URL，由 effect 发请求。这样返回、刷新、分享都能重建。
"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import type { DoubanHotItem } from "@/types";
import { api } from "@/lib/api";
import { normalizeItem } from "@/components/media/discoverUtils";
import { discoverDetailUrl, discoverSearchUrl, MOBILE_ROUTES } from "@/lib/mobile/mobileRouteUtils";
import { useMobilePlugins } from "./MobileProviders";
import MobileStateView, { type MobileViewState } from "./MobileStateView";
import MobileDiscoverGrid from "./MobileDiscoverGrid";

export interface MobileDiscoverSearchClientProps {
  /** 来自 URL 的关键词，空串表示还没搜过 */
  q: string;
}

export default function MobileDiscoverSearchClient({ q }: MobileDiscoverSearchClientProps) {
  const router = useRouter();
  const { hasDiscover, ready: pluginsReady } = useMobilePlugins();
  const [draft, setDraft] = useState(q);
  const [items, setItems] = useState<DoubanHotItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [failed, setFailed] = useState(false);
  // 同一个词不重复搜（Strict Mode 会跑两次 effect），也用于识别"换词了"
  const searchedRef = useRef("");

  // 输入框跟着 URL 走：从详情返回时框里要还留着上次搜的词
  useEffect(() => { setDraft(q); }, [q]);

  useEffect(() => {
    if (!q || !pluginsReady || !hasDiscover) return;
    if (searchedRef.current === q) return;
    searchedRef.current = q;

    let alive = true;
    setSearching(true);
    setFailed(false);
    api.doubanSearch(q)
      .then(data => {
        if (!alive) return;
        const raw = (data.candidates || data.items || []) as unknown[];
        setItems(raw.map(normalizeItem));
      })
      .catch(() => { if (alive) { setFailed(true); setItems([]); } })
      .finally(() => { if (alive) setSearching(false); });
    return () => { alive = false; };
  }, [q, pluginsReady, hasDiscover]);

  const onSubmit = useCallback((event: React.FormEvent) => {
    event.preventDefault();
    const next = draft.trim();
    if (!next) return;
    // 同词重搜：URL 不变则 effect 不会触发，这里直接重置闸门再走一次
    if (next === q) {
      searchedRef.current = "";
      setItems([]);
    }
    router.replace(discoverSearchUrl(next));
  }, [draft, q, router]);

  const onOpen = useCallback((item: DoubanHotItem) => {
    router.push(discoverDetailUrl({
      title: item.title,
      year: item.year,
      mediaType: item.media_type || "movie",
      // 豆瓣搜索的结果 douban_id 就是真的豆瓣 id，可以带
      source: "douban",
      id: item.douban_id,
      subtitle: item.subtitle,
      cnName: item.clean_name_cn,
      enName: item.clean_name_en,
      originalName: item.clean_name_original,
      cover: item.cover_url,
      localStatus: item.local_status,
      localFolder: item.local_folder,
    }));
  }, [router]);

  let state: MobileViewState = "ready";
  if (!pluginsReady) state = "loading";
  else if (searching) state = "loading";
  else if (failed) state = "error";
  else if (items.length === 0) state = "empty";

  return (
    <div className="flex flex-col gap-3 pt-3">
      <form onSubmit={onSubmit} className="flex gap-2">
        <input
          type="search"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          placeholder="搜片名，比如 沙丘"
          aria-label="片名"
          enterKeyHint="search"
          className="min-w-0 flex-1 rounded-[var(--m-radius)] px-3 text-[15px] text-[var(--m-text)] outline-none"
          style={{
            minHeight: "var(--m-touch-min)",
            background: "var(--m-surface)",
            border: "1px solid var(--m-border)",
          }}
        />
        <button
          type="submit"
          className="shrink-0 rounded-[var(--m-radius)] px-4 text-[15px] font-medium text-[var(--m-on-accent)]"
          style={{ minHeight: "var(--m-touch-min)", background: "var(--m-accent)" }}
        >
          搜索
        </button>
      </form>

      {!hasDiscover && pluginsReady ? (
        <MobileStateView
          state="empty"
          emptyText="没有安装发现插件（feature-discover），片名搜索不可用"
        />
      ) : !q ? (
        // 还没搜过：不显示空态错误，说清楚这里搜的是什么
        <p className="px-1 pt-6 text-center text-[13px] text-[var(--m-text-dim)]">
          按片名找片子，能看到评分和本地是否已有。
          <br />
          找种子和网盘资源请到片子详情里点「搜索资源」。
        </p>
      ) : (
        <MobileStateView
          state={state}
          loadingText="正在搜索…"
          emptyText={`没有找到「${q}」，换个写法试试（中文名 / 原名都行）`}
          errorText="搜索失败，检查后端与网络是否正常"
          onRetry={() => { searchedRef.current = ""; setFailed(false); router.replace(discoverSearchUrl(q)); }}
        >
          <MobileDiscoverGrid
            items={items}
            showMediaType
            hasMore={false}
            loadingMore={false}
            moreFailed={false}
            onOpen={onOpen}
            onLoadMore={() => {}}
          />
        </MobileStateView>
      )}

      {/* 资源搜索的入口在详情页，但用户可能就是想直接开一个空的资源搜索 */}
      {q && (
        <p className="px-1 pt-2 text-center text-[12px] text-[var(--m-text-dim)]">
          要直接搜种子或网盘？
          <button
            type="button"
            onClick={() => router.push(`${MOBILE_ROUTES.resource}?q=${encodeURIComponent(q)}`)}
            className="ml-1 underline"
            style={{ color: "var(--m-accent)" }}
          >
            用「{q}」搜资源
          </button>
        </p>
      )}
    </div>
  );
}
