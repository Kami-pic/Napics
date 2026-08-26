// 视频详情（移动端）。
//
// 只提供移动端范围内的三件事：播放、搜索资源、看基本信息 + 刮削信息。
// 刮削触发、改名、整理、批处理一律不渲染 —— 那些操作在手机上误触代价太高，
// 且都需要桌面才有的确认交互。
//
// 刮削数据走桌面同一个 useScrape（只用它的读取路径；rescrape 才会弹 alert，这里不调）。
"use client";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { useMobileLibraryTree } from "./MobileLibraryTreeProvider";
import {
  findVideoByPath,
  videoDisplayName,
  episodeSeasonNumber,
  episodeNumber,
  pathFileName,
} from "@/lib/mobile/libraryNav";
import { playUrl, resourceSearchUrl, libraryUrl } from "@/lib/mobile/mobileRouteUtils";
import { useScrape } from "@/components/detail/useScrape";
import MobileShell from "./MobileShell";
import MobileStateView from "./MobileStateView";
import MobilePoster from "./MobilePoster";
import MobileMediaInfoList from "./MobileMediaInfoList";
import MobileToast from "./MobileToast";

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
  const { data: scrape, reading: scrapeReading, status: scrapeStatus, reload: reloadScrape } = useScrape(
    video ? videoDisplayName(video) : "",
    video ? video.file_path : "",
    false,
  );
  const scrapeFailed = scrapeStatus === "failed";

  // 一键刮削：**只在没有刮削信息时提供**。已有刮削的条目不给任何覆盖入口 ——
  // 手机上误触一下就把整理好的 NFO 和海报冲掉，没有撤销路径。
  //
  // 不复用 useScrape 的 rescrape()：它失败时弹 alert（桌面写法），
  // 移动端要走 toast。这里直接调同一个端点。
  const [scraping, setScraping] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const runScrape = useCallback(async () => {
    if (!video || scraping) return;
    setScraping(true);
    setToast(null);
    try {
      const res = await api.executeScrape(video.file_path);
      const data = res.self?.data || res.data;
      const confidence = res.self?.confidence || res.confidence;
      if (data?.tmdb_id || data?.title) {
        await reloadScrape();
        // 桌面对 low / medium 会要求用户确认后才算数，移动端没有重新匹配入口，
        // 至少要说清楚"这个结果可能不对"，否则用户以为刮削成功了
        const shaky = confidence?.level === "low" || confidence?.level === "medium";
        setToast(shaky
          ? { msg: `刮削完成，但匹配置信度${confidence?.level === "low" ? "很低" : "一般"}，建议在桌面端核对`, ok: false }
          : { msg: "刮削完成", ok: true });
      } else {
        setToast({ msg: "没有匹配到结果，需要在桌面端手动重新匹配", ok: false });
      }
    } catch {
      setToast({ msg: "刮削请求失败，检查后端与 TMDB 配置", ok: false });
    } finally {
      setScraping(false);
    }
  }, [video, scraping, reloadScrape]);

  const openPlay = useCallback(() => {
    router.push(playUrl(path));
  }, [router, path]);

  const openSearch = useCallback(() => {
    // 树还没到位时用文件名兜底：清洗名要等树，但"能搜"比"搜得准"更要紧
    if (!video) {
      router.push(resourceSearchUrl({ q: pathFileName(path), tab: "bt" }));
      return;
    }
    router.push(resourceSearchUrl({
      q: video.clean_name_cn || video.clean_name || video.file_name,
      tab: "bt",
      cnName: video.clean_name_cn,
      enName: video.clean_name_en,
      originalName: video.clean_name_original,
      mediaType: scrape?.media_type,
      season: episodeSeasonNumber(video.file_name) ?? undefined,
      resolution: video.resolution,
    }));
  }, [router, video, scrape, path]);

  // 返回上一级：视频所在目录。直达进来时历史栈里没有列表页
  const parentDir = path.replace(/[\\/][^\\/]+$/, "");
  const onBack = useCallback(() => {
    router.push(libraryUrl(parentDir));
  }, [router, parentDir]);

  // **不整页等整树**：`/library/tree` 实测 2.43 MiB 未压缩，等它到了再渲染就是
  // "点进去先白屏几秒"。文件名从 path 就能取，播放按钮也只需要 path ——
  // 这两样第一帧就能给。树到位之后再补规格、刮削和搜索上下文。
  const fallbackName = pathFileName(path);
  let state: "loading" | "error" | "ready" = "ready";
  let errorText = "";
  if (!path) {
    state = "error";
    errorText = "缺少视频路径，无法打开详情";
  } else if (ready && loadFailed) {
    state = "error";
    errorText = "媒体库加载失败，检查后端是否在运行";
  } else if (ready && !video) {
    state = "error";
    errorText = "这个视频不在媒体库里，可能已被移动或删除。同步一次再试";
  }

  const title = video ? videoDisplayName(video) : fallbackName || "详情";
  // 从"季 → 集"点进来后，标题往往只剩剧名，用户看不出这是第几集。
  // 树没到位时用文件名解析，结果一样
  const seasonNo = episodeSeasonNumber(video?.file_name || fallbackName);
  const episodeNo = episodeNumber(video?.file_name || fallbackName);
  const episodeLabel = seasonNo !== null && episodeNo !== null
    ? `S${String(seasonNo).padStart(2, "0")}E${String(episodeNo).padStart(2, "0")}`
    : "";

  // 错误态要有出口：树里找不到这个视频时，用户能做的是回媒体库或去同步
  const errorAction = (
    <button
      type="button"
      onClick={() => router.push(libraryUrl(parentDir))}
      className="rounded-[var(--m-radius-sm)] px-4 text-sm text-[var(--m-text)]"
      style={{ minHeight: "var(--m-touch-min)", background: "var(--m-surface-raised)" }}
    >
      回媒体库
    </button>
  );

  return (
    // 页头放剧名/片名（刮削标题优先），正文 h2 放"季集 + 本文件的清洗名" ——
    // 两处都填同一个字符串的话，60px 内会出现两遍一样的标题。
    <MobileShell
      title={scrape?.title || title}
      subtitle={episodeLabel || undefined}
      onBack={path ? onBack : undefined}
    >
      <MobileStateView
        state={state}
        loadingText="正在读取媒体库…"
        errorText={errorText}
        errorAction={errorAction}
      >
        {path && state === "ready" && (
          <div className="flex flex-col gap-4 pt-3">
            <div className="flex gap-3">
              <MobilePoster
                localPath={path}
                remoteUrl={scrape?.poster_url}
                fallbackText={title}
              />
              <div className="min-w-0 flex-1">
                <h2 className="text-[16px] font-semibold text-[var(--m-text)]">
                  {episodeLabel ? `${episodeLabel} · ${title}` : title}
                </h2>
                <p className="mt-1 flex flex-wrap gap-x-2 text-[12px] text-[var(--m-text-dim)]">
                  {scrape?.year && <span>{scrape.year}</span>}
                  {scrape?.rating ? <span>TMDB {scrape.rating.toFixed(1)}</span> : null}
                  {scrape?.genres?.length ? <span>{scrape.genres.slice(0, 3).join(" / ")}</span> : null}
                </p>
                {/* 用 reading 而不是 status：status 的 idle 既是"还没读"也是
                    "读完了没有数据"，用它判断会让每次进页面都先闪一下"没有刮削信息" */}
                {scrapeReading && (
                  <p className="mt-2 text-[12px] text-[var(--m-text-dim)]">正在读取刮削信息…</p>
                )}
                {/* 读取失败 ≠ 没有刮削。
                    `/scrape/execute` 是 force=True，而且传文件路径时若同目录只有一个视频
                    还会升级成整个目录刮削（覆盖目录级 NFO 与 poster.jpg）。
                    所以后端不可达/超时的时候**绝不能**给刮削按钮 —— 那台机器上可能本来
                    有一份好好的刮削结果，只是这次读不到。只给"重试读取"。 */}
                {!scrapeReading && !scrape && scrapeFailed && (
                  <div className="mt-2 flex flex-col items-start gap-2">
                    <p className="text-[12px] text-[var(--m-text-dim)]">
                      刮削信息读取失败，可能是后端不可达或路径暂时读不到。
                      这时不提供刮削，避免覆盖掉本来就有的结果。
                    </p>
                    <button
                      type="button"
                      onClick={() => { void reloadScrape(); }}
                      className="rounded-[var(--m-radius-sm)] px-3 text-[13px] text-[var(--m-text)]"
                      style={{
                        minHeight: "var(--m-touch-min)",
                        background: "var(--m-surface-raised)",
                        border: "1px solid var(--m-border)",
                      }}
                    >
                      重试读取
                    </button>
                  </div>
                )}

                {/* 确认过"这个条目没有刮削"才给一键刮削。有刮削则什么操作都不提供 */}
                {!scrapeReading && !scrape && !scrapeFailed && (
                  <div className="mt-2 flex flex-col items-start gap-2">
                    <p className="text-[12px] text-[var(--m-text-dim)]">
                      还没有刮削信息（简介、海报、评分都来自刮削）
                    </p>
                    <button
                      type="button"
                      onClick={() => { void runScrape(); }}
                      disabled={scraping}
                      className="rounded-[var(--m-radius-sm)] px-3 text-[13px] text-[var(--m-text)] disabled:opacity-60"
                      style={{
                        minHeight: "var(--m-touch-min)",
                        background: "var(--m-surface-raised)",
                        border: "1px solid var(--m-border)",
                      }}
                    >
                      {scraping ? "刮削中…" : "一键刮削"}
                    </button>
                  </div>
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

            {/* 规格信息要等整树（分辨率、大小、时长都在树上的 video 对象里） */}
            {video ? (
              <MobileMediaInfoList video={video} />
            ) : (
              <p className="text-[12px] text-[var(--m-text-dim)]" role="status">
                正在读取媒体库，规格信息稍后显示…
              </p>
            )}
          </div>
        )}
      </MobileStateView>
      {toast && (
        <MobileToast message={toast.msg} ok={toast.ok} onDismiss={() => setToast(null)} />
      )}
    </MobileShell>
  );
}
