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
import { useCallback, useEffect, useRef, useState, type SyntheticEvent } from "react";
import { useRouter } from "next/navigation";

import { useMobilePlugins } from "./MobileProviders";
import {
  buildStreamUrl,
  buildSubtitleListUrl,
  resolveSubtitleUrl,
  canPlayNatively,
  videoExtension,
  isCrossOriginBackend,
} from "@/lib/domain/playback";
import { libraryUrl } from "@/lib/mobile/mobileRouteUtils";
import MobileStateView from "./MobileStateView";
import MobileSubtitleSwitch from "./MobileSubtitleSwitch";

/** 只保留能直接喂给 <track> 的：外挂 + 可渲染 */
export interface PlayableSubtitle {
  name: string;
  /** 合法 BCP-47 两字母码；识别不出时为空串（不编造） */
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

// 后端 _normalize_lang 已经把常见写法归到两字母码，但识别不出的后缀是**原样返回**的
// （`movie.简体.srt` → lang "简体"）。非法值塞进 srclang，iOS 的字幕菜单可能不列该轨，
// 所以这里过一道白名单，过不了就留空。
const VALID_SRC_LANGS = new Set([
  "zh", "en", "ja", "ko", "fr", "de", "es", "pt", "ru", "it",
  "th", "vi", "ar", "hi", "id", "ms", "nl",
]);

function normalizeSrcLang(lang?: string): string {
  const value = (lang || "").toLowerCase().trim();
  return VALID_SRC_LANGS.has(value) ? value : "";
}

/**
 * 过滤字幕轨。
 *
 * `embedded` 的要走 `/playback/subtitle/extract`，那是一次全量 demux（实测约
 * 5.8 秒/GB），移动端不碰。`unsupported` 是图形字幕（PGS/VobSub），是图片不是文本。
 *
 * 语言识别不出时**留空而不是兜成 zh**：`movie.srt` 这种无后缀字幕很可能是英文，
 * 标成中文会让 iOS 按系统语言自动选轨时选错。
 */
export function pickExternalSubtitles(items: SubtitleApiItem[]): PlayableSubtitle[] {
  return (items || [])
    .filter(item => !item.embedded && !item.unsupported && !!item.url)
    .map((item, idx) => ({
      name: item.name || `字幕 ${idx + 1}`,
      lang: normalizeSrcLang(item.lang),
      url: resolveSubtitleUrl(item.url!),
    }));
}

/** SSR 期没有 document，退化成只看扩展名 */
function probeNative(path: string): boolean {
  if (typeof document === "undefined") return canPlayNatively(path, null);
  return canPlayNatively(path, document.createElement("video"));
}

/** 每个视频一份状态。换 path 必须整份重置，否则上一个视频的报错会盖在新视频上 */
interface PlaybackState {
  key: string;
  nativeSupported: boolean;
  subtitles: PlayableSubtitle[];
  notice: string;
  error: string;
  /** -1 = 关闭字幕 */
  activeSubtitle: number;
}

function initState(path: string): PlaybackState {
  return {
    key: path,
    nativeSupported: probeNative(path),
    subtitles: [],
    notice: "",
    error: "",
    activeSubtitle: 0,
  };
}

export interface MobileNativePlayerProps {
  path: string;
}

export default function MobileNativePlayer({ path }: MobileNativePlayerProps) {
  const router = useRouter();
  const { hasPlayer, ready: pluginsReady } = useMobilePlugins();
  const videoRef = useRef<HTMLVideoElement>(null);

  // 换视频时整份重置。用"渲染期比对上次 props"而不是 effect 里 setState：
  // effect 慢一帧，那一帧里新视频顶上还挂着旧视频的报错。
  const [state, setState] = useState(() => initState(path));
  if (state.key !== path) setState(initState(path));
  const current = state.key === path ? state : initState(path);

  const patch = useCallback((updates: Partial<PlaybackState>) => {
    setState(prev => (prev.key === path ? { ...prev, ...updates } : prev));
  }, [path]);

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
        const total = (data?.subtitles || []).length;
        let notice = "";
        if (picked.length === 0 && total > 0) {
          notice = "这个文件只有内封或图形字幕，手机端不提取，用桌面端播放可以看";
        } else if (picked.length === 0 && data?.summary?.maybe_hardcoded) {
          notice = "没有字幕轨，画面上若有字幕则是压进画面的硬字幕";
        }
        setState(prev => (prev.key === path ? { ...prev, subtitles: picked, notice } : prev));
      } catch (e) {
        if (!cancelled && (e as Error).name !== "AbortError") {
          setState(prev => (
            prev.key === path ? { ...prev, notice: "字幕列表获取失败，视频仍可播放" } : prev
          ));
        }
      }
    })();

    return () => { cancelled = true; controller.abort(); };
  }, [path, hasPlayer]);

  const selectSubtitle = useCallback((index: number) => {
    patch({ activeSubtitle: index });
    const tracks = videoRef.current?.textTracks;
    if (!tracks) return;
    for (let i = 0; i < tracks.length; i++) {
      tracks[i].mode = i === index ? "showing" : "disabled";
    }
  }, [patch]);

  const onError = useCallback((event: SyntheticEvent<HTMLVideoElement>) => {
    const video = event.currentTarget;
    // 换视频时 React 只改 src，元素不卸载，旧资源被中断时还会补一次 error。
    // 不校验来源就会对着能播的新视频报"编码不受支持"。
    // 1 = MEDIA_ERR_ABORTED。用字面量而不是 MediaError.MEDIA_ERR_ABORTED：
    // 那个全局在 jsdom 里不存在，引用它会让 handler 抛 ReferenceError。
    if (video.error?.code === 1) return;
    if (video.currentSrc && !video.currentSrc.endsWith(buildStreamUrl(path))) return;
    patch({
      error: `这个文件的编码不受浏览器支持（${videoExtension(path) || "未知格式"}），用桌面端播放`,
    });
  }, [patch, path]);

  const backToLibrary = (
    <button
      type="button"
      onClick={() => router.push(libraryUrl())}
      className="rounded-lg px-4 text-sm text-[var(--m-text)]"
      style={{ minHeight: "var(--m-touch-min)", background: "var(--m-surface-raised)" }}
    >
      回媒体库
    </button>
  );

  if (!path) {
    return <MobileStateView state="error" errorText="缺少视频路径，无法播放" errorAction={backToLibrary} />;
  }
  if (!pluginsReady) {
    return <MobileStateView state="loading" loadingText="正在检查播放能力…" />;
  }
  if (!hasPlayer) {
    return (
      <MobileStateView
        state="error"
        errorText="播放插件（feature-player）未安装或不可用，无法播放"
        errorAction={backToLibrary}
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <video
        data-testid="mobile-video"
        ref={videoRef}
        src={buildStreamUrl(path)}
        controls
        playsInline
        preload="metadata"
        // 只在跨源部署下加：那时不加，<track> 会被静默拒绝加载（字幕条数正常但
        // 一个字都不出）。**同源下不能加** —— 它会把媒体请求变成 CORS 模式，
        // anonymous 不发 cookie，开了访问密码后连视频本体都 401。
        {...(isCrossOriginBackend() ? { crossOrigin: "anonymous" as const } : {})}
        onError={onError}
        className="max-h-[70dvh] w-full bg-black"
      >
        {current.subtitles.map((sub, idx) => (
          <track
            key={sub.url}
            kind="subtitles"
            label={sub.name}
            {...(sub.lang ? { srcLang: sub.lang } : {})}
            src={sub.url}
            default={idx === current.activeSubtitle}
          />
        ))}
      </video>

      <div className="flex flex-col gap-2 px-[var(--m-page-px)]">
        {current.error && (
          <p role="alert" className="text-[13px] text-[var(--m-danger)]">{current.error}</p>
        )}
        {/* 这条是首帧就存在的页面状态，不是刚发生的事件 —— 用 status 不用 alert，
            assertive 打断留给真正的运行期错误（上面那条 current.error） */}
        {!current.error && !current.nativeSupported && (
          <p role="status" className="text-[13px] text-[var(--m-warning)]">
            浏览器可能无法播放这个格式（{videoExtension(path) || "未知格式"}），
            如果一直黑屏请用桌面端
          </p>
        )}
        {current.notice && (
          <p className="text-[12px] text-[var(--m-text-dim)]">{current.notice}</p>
        )}
        <MobileSubtitleSwitch
          names={current.subtitles.map(sub => sub.name)}
          activeIndex={current.activeSubtitle}
          onSelect={selectSubtitle}
        />
      </div>
    </div>
  );
}
