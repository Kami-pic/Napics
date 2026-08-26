// 发现详情（移动端）。
//
// 榜单条目不落盘，这一页的全部输入都来自 URL —— 刷新和直达都能重建，
// 不依赖"上一页给我塞了个对象"。详情数据走桌面同一个 /media/info 和同一份
// localStorage 缓存（key 是 title_year_source），两端互相受益。
//
// 只有两个出口：搜索资源、查看本地。订阅、入库、刮削一律不在移动端做。
"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import {
  proxyUrl,
  getCachedDetail,
  setCachedDetail,
  type MediaDetail,
} from "@/components/media/discoverUtils";
import {
  discoverUrl,
  libraryUrl,
  searchUrl,
  type MobileDiscoverDetailQuery,
} from "@/lib/mobile/mobileRouteUtils";
import MobileShell from "./MobileShell";
import MobileStateView from "./MobileStateView";
import MobileDiscoverDetailInfo from "./MobileDiscoverDetailInfo";

export interface MobileDiscoverDetailClientProps {
  query: MobileDiscoverDetailQuery;
}

/** 详情读取超时。超时后按"读取失败"处理，标题和清洗名都在 URL 里，搜索资源仍可用 */
const DETAIL_TIMEOUT_MS = 15_000;

/** 远程海报 + 文字占位。发现侧没有本地文件，所以不走 MobilePoster 的本地优先链 */
function RemotePoster({ url, fallbackText }: { url?: string; fallbackText: string }) {
  const [failed, setFailed] = useState(false);
  const src = url && !failed ? proxyUrl(url) : "";
  return (
    <div
      className="flex w-24 shrink-0 items-center justify-center overflow-hidden rounded-[var(--m-radius)]"
      style={{ aspectRatio: "2 / 3", background: "var(--m-surface-raised)" }}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element -- 走后端图片代理，不进 next/image
        <img src={src} alt="" className="h-full w-full object-cover" onError={() => setFailed(true)} />
      ) : (
        <span className="px-2 text-center text-[11px] leading-tight text-[var(--m-text-dim)]">
          {fallbackText}
        </span>
      )}
    </div>
  );
}

interface DetailState {
  /** 这份状态属于哪个 title_year_source */
  key: string;
  detail: MediaDetail | null;
  loading: boolean;
  failed: boolean;
}

/** 缓存命中就直接是初始值：放到 effect 里 setState 会白渲染一帧空态 */
function initialDetailState(key: string, title: string): DetailState {
  const cached = title ? getCachedDetail(key) : undefined;
  return { key, detail: cached ?? null, loading: Boolean(title) && !cached, failed: false };
}

export default function MobileDiscoverDetailClient({ query }: MobileDiscoverDetailClientProps) {
  const router = useRouter();

  const { title, year, mediaType, source, id, subtitle, tab, localStatus, localFolder } = query;
  const detailSource = source || "tmdb";
  const cacheKey = `${title}_${year || ""}_${detailSource}`;

  // 换片子要重置整份状态。用"渲染期比对上次 key"而不是 effect 里 setState，
  // 和 MobilePoster 同一个手法：effect 里同步 setState 会多渲染一帧。
  const [tracked, setTracked] = useState(() => initialDetailState(cacheKey, title));
  if (tracked.key !== cacheKey) setTracked(initialDetailState(cacheKey, title));
  const { detail, loading, failed } = tracked.key === cacheKey
    ? tracked
    : initialDetailState(cacheKey, title);

  // Strict Mode 下 effect 跑两次，没有这个闸门会打两次 /media/info
  const requestedKeyRef = useRef("");

  useEffect(() => {
    if (!title) return;
    if (requestedKeyRef.current === cacheKey) return;
    requestedKeyRef.current = cacheKey;
    // 缓存命中的那份已经在初始状态里了
    if (getCachedDetail(cacheKey)) return;

    let alive = true;
    // /media/info 会串行问 TMDB / 豆瓣 / Bangumi 三家，弱网下可能很久不返回。
    // 没有超时的话页面就一直停在 loading，连"搜索资源"都点不到（子树还没渲染）。
    const timer = setTimeout(() => {
      if (alive) setTracked({ key: cacheKey, detail: null, loading: false, failed: true });
    }, DETAIL_TIMEOUT_MS);

    api.mediaInfo(title, year || "", mediaType === "tv" ? "tv" : "movie", subtitle || "", detailSource, id || "")
      .then((d: MediaDetail) => {
        if (!alive) return;
        if (d?.found) setCachedDetail(cacheKey, d);
        setTracked({ key: cacheKey, detail: d || { found: false }, loading: false, failed: false });
      })
      .catch(() => {
        if (alive) setTracked({ key: cacheKey, detail: null, loading: false, failed: true });
      })
      .finally(() => clearTimeout(timer));
    return () => { alive = false; clearTimeout(timer); };
  }, [title, year, mediaType, subtitle, detailSource, id, cacheKey]);

  const onBack = useCallback(() => {
    // 从哪个榜单进来的就回那个榜单。直达进来时 tab 为空，落回默认榜单
    router.push(discoverUrl(tab));
  }, [router, tab]);

  const openSearch = useCallback(() => {
    router.push(searchUrl({
      q: query.cnName || title,
      tab: "bt",
      cnName: query.cnName || title,
      // 详情里的英文名/原名比榜单条目更全，优先用它
      enName: query.enName || detail?.english_title || undefined,
      originalName: query.originalName || detail?.original_title || undefined,
      mediaType: mediaType,
    }));
  }, [router, query, title, mediaType, detail]);

  const openLocal = useCallback(() => {
    if (!localFolder) return;
    router.push(libraryUrl(localFolder));
  }, [router, localFolder]);

  const hasLocal = Boolean(localFolder) && localStatus !== "none" && Boolean(localStatus);
  const notFound = Boolean(detail) && !detail?.found;

  // **详情永不阻塞整页**：/media/info 要串行问 TMDB / 豆瓣 / Bangumi，实测冷缓存 6 秒
  // 起步，弱网更久。整页 loading 会让"搜索资源""查看本地"这两个本来就不依赖详情的
  // 出口也点不到，用户看到的就是"点进去转圈几十秒然后失败"。
  // 骨架（标题 / 年份 / 卡片海报 / 两个按钮）全部来自 URL，第一帧就能用。
  let state: "loading" | "error" | "ready" = "ready";
  let errorText = "";
  if (!title) {
    state = "error";
    errorText = "缺少影片信息，无法打开详情";
  }

  const errorAction = (
    <button
      type="button"
      onClick={onBack}
      className="rounded-[var(--m-radius-sm)] px-4 text-sm text-[var(--m-text)]"
      style={{ minHeight: "var(--m-touch-min)", background: "var(--m-surface-raised)" }}
    >
      回发现
    </button>
  );

  return (
    <MobileShell
      title={detail?.title || title || "详情"}
      subtitle={year || undefined}
      onBack={onBack}
    >
      <MobileStateView
        state={state}
        loadingText="正在读取影片信息…"
        errorText={errorText}
        errorAction={errorAction}
      >
        {title && (
          <div className="flex flex-col gap-4 pt-3">
            <div className="flex gap-3">
              {/* 详情的海报更大更全，但要等 6 秒；先用榜单卡片那张顶上 */}
              <RemotePoster url={detail?.poster_url || query.cover} fallbackText={title} />
              <div className="min-w-0 flex-1">
                <h2 className="text-[16px] font-semibold text-[var(--m-text)]">
                  {detail?.title || title}
                </h2>
                {(detail?.original_title || query.originalName || query.enName) && (
                  <p className="mt-0.5 truncate text-[12px] text-[var(--m-text-dim)]">
                    {detail?.original_title || query.originalName || query.enName}
                  </p>
                )}
                {loading && (
                  <p className="mt-2 text-[12px] text-[var(--m-text-dim)]" role="status">
                    正在读取影片信息…
                  </p>
                )}
                {failed && (
                  <p className="mt-2 text-[12px] text-[var(--m-text-dim)]">
                    影片信息读取失败，仍可直接搜索资源
                  </p>
                )}
                {notFound && !failed && (
                  <p className="mt-2 text-[12px] text-[var(--m-text-dim)]">
                    三个元数据源都没匹配到这部片子，仍可直接搜索资源
                  </p>
                )}
              </div>
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={openSearch}
                className="flex flex-1 items-center justify-center gap-2 rounded-[var(--m-radius)] text-[15px] font-medium text-[var(--m-on-accent)]"
                style={{ minHeight: "var(--m-touch-min)", background: "var(--m-accent)" }}
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
                搜索资源
              </button>
              {hasLocal && (
                <button
                  type="button"
                  onClick={openLocal}
                  className="flex flex-1 items-center justify-center gap-2 rounded-[var(--m-radius)] text-[15px] text-[var(--m-text)]"
                  style={{
                    minHeight: "var(--m-touch-min)",
                    background: "var(--m-surface)",
                    border: "1px solid var(--m-border)",
                  }}
                >
                  {localStatus === "owned_low" ? "本地已有（可升级）" : "查看本地"}
                </button>
              )}
            </div>

            {detail?.found && <MobileDiscoverDetailInfo detail={detail} />}
          </div>
        )}
      </MobileStateView>
    </MobileShell>
  );
}
