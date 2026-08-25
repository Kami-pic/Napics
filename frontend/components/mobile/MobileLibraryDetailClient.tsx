// 视频详情（移动端）。
//
// 只提供移动端范围内的三件事：播放、搜索资源、看基本信息 + 刮削信息。
// 刮削触发、改名、整理、批处理一律不渲染 —— 那些操作在手机上误触代价太高，
// 且都需要桌面才有的确认交互。
//
// 刮削数据走桌面同一个 useScrape（只用它的读取路径；rescrape 才会弹 alert，这里不调）。
"use client";
import { useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";

import { useMobileLibraryTree } from "./MobileLibraryTreeProvider";
import { findVideoByPath, videoDisplayName, episodeSeasonNumber } from "@/lib/mobile/libraryNav";
import { playUrl, searchUrl, libraryUrl } from "@/lib/mobile/mobileRouteUtils";
import { useScrape } from "@/components/detail/useScrape";
import MobileShell from "./MobileShell";
import MobileStateView from "./MobileStateView";
import MobilePoster from "./MobilePoster";
import MobileMediaInfoList from "./MobileMediaInfoList";

export interface MobileLibraryDetailClientProps {
  path: string;
}

export default function MobileLibraryDetailClient({ path }: MobileLibraryDetailClientProps) {
  const router = useRouter();
  // 详情页也得自己触发树加载：Provider 挂在 layout 上但不自动拉
  const { tree, ready, loadFailed, ensureLoaded } = useMobileLibraryTree();
  useEffect(() => { ensureLoaded(); }, [ensureLoaded]);

  const video = ready && !loadFailed ? findVideoByPath(tree, path) : null;

  // useScrape 在 path 为空时不发请求，可以无条件调用（hook 不能有条件调用）
  const { data: scrape, status: scrapeStatus } = useScrape(
    video ? videoDisplayName(video) : "",
    video ? video.file_path : "",
    false,
  );

  const openPlay = useCallback(() => {
    router.push(playUrl(path));
  }, [router, path]);

  const openSearch = useCallback(() => {
    if (!video) return;
    router.push(searchUrl({
      q: video.clean_name_cn || video.clean_name || video.file_name,
      tab: "bt",
      cnName: video.clean_name_cn,
      enName: video.clean_name_en,
      originalName: video.clean_name_original,
      mediaType: scrape?.media_type,
      season: episodeSeasonNumber(video.file_name) ?? undefined,
      resolution: video.resolution,
    }));
  }, [router, video, scrape]);

  // 返回上一级：视频所在目录。直达进来时历史栈里没有列表页
  const parentDir = path.replace(/[\\/][^\\/]+$/, "");
  const onBack = useCallback(() => {
    router.push(libraryUrl(parentDir));
  }, [router, parentDir]);

  let state: "loading" | "error" | "ready" = "ready";
  let errorText = "";
  if (!path) {
    state = "error";
    errorText = "缺少视频路径，无法打开详情";
  } else if (!ready) {
    state = "loading";
  } else if (loadFailed) {
    state = "error";
    errorText = "媒体库加载失败，检查后端是否在运行";
  } else if (!video) {
    state = "error";
    errorText = "这个视频不在媒体库里，可能已被移动或删除。同步一次再试";
  }

  const title = video ? videoDisplayName(video) : "详情";

  return (
    <MobileShell title={title} subtitle={scrape?.title || undefined} onBack={path ? onBack : undefined}>
      <MobileStateView state={state} loadingText="正在读取媒体库…" errorText={errorText}>
        {video && (
          <div className="flex flex-col gap-4 pt-3">
            <div className="flex gap-3">
              <MobilePoster
                localPath={video.file_path}
                remoteUrl={scrape?.poster_url}
                fallbackText={title}
              />
              <div className="min-w-0 flex-1">
                <h2 className="text-[16px] font-semibold text-[var(--m-text)]">{scrape?.title || title}</h2>
                <p className="mt-1 flex flex-wrap gap-x-2 text-[12px] text-[var(--m-text-dim)]">
                  {scrape?.year && <span>{scrape.year}</span>}
                  {scrape?.rating ? <span>TMDB {scrape.rating.toFixed(1)}</span> : null}
                  {scrape?.genres?.length ? <span>{scrape.genres.slice(0, 3).join(" / ")}</span> : null}
                </p>
                {scrapeStatus === "loading" && (
                  <p className="mt-2 text-[12px] text-[var(--m-text-dim)]">正在读取刮削信息…</p>
                )}
                {scrapeStatus !== "success" && scrapeStatus !== "loading" && (
                  <p className="mt-2 text-[12px] text-[var(--m-text-dim)]">
                    没有刮削信息（在桌面端整理后这里会显示简介与海报）
                  </p>
                )}
              </div>
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={openPlay}
                className="flex flex-1 items-center justify-center gap-2 rounded-[var(--m-radius)] text-[15px] font-medium text-[var(--m-on-accent)]"
                style={{ minHeight: "var(--m-touch-min)", background: "var(--m-accent)" }}
              >
                <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M8 5v14l11-7z" />
                </svg>
                播放
              </button>
              <button
                type="button"
                onClick={openSearch}
                className="flex flex-1 items-center justify-center gap-2 rounded-[var(--m-radius)] text-[15px] text-[var(--m-text)]"
                style={{
                  minHeight: "var(--m-touch-min)",
                  background: "var(--m-surface)",
                  border: "1px solid var(--m-border)",
                }}
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
                搜索资源
              </button>
            </div>

            {scrape?.overview && (
              <p className="text-[13px] leading-relaxed text-[var(--m-text-muted)]">{scrape.overview}</p>
            )}

            <MobileMediaInfoList video={video} />
          </div>
        )}
      </MobileStateView>
    </MobileShell>
  );
}
