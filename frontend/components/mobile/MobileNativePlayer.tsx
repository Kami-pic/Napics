// 移动端原生播放器。
//
// 只做一件事：把 /playback/stream 交给系统播放器。刻意不做的：
// - **不转码**。手机端转码会把 NAS 的 CPU 打满，且 iOS Safari 对 fMP4 分片流的
//   兼容性要真机逐个验证。不能原生播的片子明确告诉用户，不悄悄退化。
// - **不自动播放**。iOS 要求用户手势，路由后 autoplay 一定被拦；依赖它会变成
//   "黑屏且没有任何提示"。用系统 controls 的播放按钮起播。
// - **不读 config.use_local_player**。那是让服务端拿本机播放器开窗口的桌面功能，
//   手机上点了什么都不会发生。
// - **不做 Blob 字幕和内嵌字幕提取**。内嵌提取要全量 demux 整个文件；
//   外挂字幕后端已经转好 WebVTT，直接给 <track> 用 URL 就行。
"use client";
import { useCallback, useEffect, useState } from "react";

import { useMobilePlugins } from "./MobileProviders";
import {
  buildStreamUrl,
  buildSubtitleListUrl,
  resolveSubtitleUrl,
  canPlayNatively,
  videoExtension,
} from "@/lib/domain/playback";
import MobileStateView from "./MobileStateView";

/** 只保留能直接喂给 <track> 的：外挂 + 可渲染 */
export interface PlayableSubtitle {
  name: string;
  lang: string;
  url: string;
}

interface SubtitleApiItem {
  name?: string;
  lang?: string;
  url?: string;
  embedded?: boolean;
  unsupported?: boolean;
}

/**
 * 过滤字幕轨。
 *
 * `embedded` 的要走 `/playback/subtitle/extract`，那是一次全量 demux（实测约
 * 5.8 秒/GB），移动端不碰。`unsupported` 是图形字幕（PGS/VobSub），是图片不是文本。
 */
export function pickExternalSubtitles(items: SubtitleApiItem[]): PlayableSubtitle[] {
  return (items || [])
    .filter(item => !item.embedded && !item.unsupported && !!item.url)
    .map((item, idx) => ({
      name: item.name || `字幕 ${idx + 1}`,
      lang: item.lang || "zh",
      url: resolveSubtitleUrl(item.url!),
    }));
}

/** SSR 期没有 document，退化成只看扩展名 */
function probeNative(path: string): boolean {
  if (typeof document === "undefined") return canPlayNatively(path, null);
  return canPlayNatively(path, document.createElement("video"));
}

export interface MobileNativePlayerProps {
  path: string;
}

export default function MobileNativePlayer({ path }: MobileNativePlayerProps) {
  const { hasPlayer, ready: pluginsReady } = useMobilePlugins();
  const [subtitles, setSubtitles] = useState<PlayableSubtitle[]>([]);
  const [subtitleNotice, setSubtitleNotice] = useState("");
  const [playbackError, setPlaybackError] = useState("");
  // 可播性判定：用**离屏** video 元素问 canPlayType，不用挂载后的 ref。
  // 走 ref 就得在 effect 里 setState，多渲染一帧还会被 react-hooks 规则拦。
  const [support, setSupport] = useState(() => ({ key: path, ok: probeNative(path) }));
  if (support.key !== path) setSupport({ key: path, ok: probeNative(path) });
  const unsupportedByBrowser = support.key === path ? !support.ok : !probeNative(path);

  useEffect(() => {
    if (!path || !hasPlayer) return;
    let cancelled = false;
    const controller = new AbortController();

    (async () => {
      try {
        const res = await fetch(buildSubtitleListUrl(path), { signal: controller.signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        const picked = pickExternalSubtitles(data?.subtitles || []);
        setSubtitles(picked);
        const total = (data?.subtitles || []).length;
        if (picked.length === 0 && total > 0) {
          setSubtitleNotice("这个文件只有内封或图形字幕，手机端不提取，用桌面端播放可以看");
        } else if (picked.length === 0 && data?.summary?.maybe_hardcoded) {
          setSubtitleNotice("没有字幕轨，画面上若有字幕则是压进画面的硬字幕");
        }
      } catch (e) {
        if (!cancelled && (e as Error).name !== "AbortError") {
          setSubtitleNotice("字幕列表获取失败，视频仍可播放");
        }
      }
    })();

    return () => { cancelled = true; controller.abort(); };
  }, [path, hasPlayer]);

  const onError = useCallback(() => {
    setPlaybackError(
      `这个文件的编码不受浏览器支持（${videoExtension(path) || "未知格式"}），用桌面端播放`,
    );
  }, [path]);

  if (!path) {
    return <MobileStateView state="error" errorText="缺少视频路径，无法播放" />;
  }
  if (pluginsReady && !hasPlayer) {
    return (
      <MobileStateView
        state="error"
        errorText="播放插件（feature-player）未安装或不可用，无法播放"
      />
    );
  }
  if (!pluginsReady) {
    return <MobileStateView state="loading" loadingText="正在检查播放能力…" />;
  }

  return (
    <div className="flex flex-col gap-3">
      <video
        data-testid="mobile-video"
        src={buildStreamUrl(path)}
        controls
        playsInline
        preload="metadata"
        onError={onError}
        className="max-h-[70dvh] w-full bg-black"
      >
        {subtitles.map((sub, idx) => (
          <track
            key={sub.url}
            kind="subtitles"
            label={sub.name}
            srcLang={sub.lang}
            src={sub.url}
            default={idx === 0}
          />
        ))}
      </video>

      <div className="flex flex-col gap-2 px-[var(--m-page-px)]">
        {playbackError && (
          <p role="alert" className="text-[13px] text-[var(--m-danger)]">{playbackError}</p>
        )}
        {!playbackError && unsupportedByBrowser && (
          <p role="alert" className="text-[13px] text-[var(--m-warning)]">
            浏览器可能无法播放这个格式（{videoExtension(path) || "未知格式"}），
            如果一直黑屏请用桌面端
          </p>
        )}
        {subtitleNotice && (
          <p className="text-[12px] text-[var(--m-text-dim)]">{subtitleNotice}</p>
        )}
        {subtitles.length > 0 && (
          <p className="text-[12px] text-[var(--m-text-dim)]">
            外挂字幕 {subtitles.length} 条，用播放器自带的字幕按钮切换
          </p>
        )}
      </div>
    </div>
  );
}
