// 全局视频播放器弹窗
// mp4/webm：原生 controls + Blob URL <track> 字幕（浏览器内置 CC 按钮）
// mkv/ts/avi：自制控制栏 + SubtitleOverlay 覆盖层渲染字幕
"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { BASE_URL } from "@/lib/api/base";
import { TranscodeProgressBar } from "./TranscodeProgressBar";
import { SubtitleOverlay } from "./SubtitleOverlay";
import { SubtitlePicker } from "./SubtitlePicker";

// 字幕轨元信息 + 懒加载状态。
// 内嵌字幕提取要把整个视频 demux 一遍（实测约 5.8 秒/GB），
// 所以只有外挂字幕在打开时立即加载，内嵌字幕等用户选中才拉。
// external=独立字幕文件，embedded=封装在视频里的文本字幕流，
// graphic=封装在视频里的图形字幕（PGS/VobSub，需 OCR 才能变文本）。
// 还有一类"硬字幕"是压进画面像素的，ffprobe 检测不到，只能在无字幕流时提示。
type SubtitleKind = "external" | "embedded" | "graphic";

interface SubtitleData {
  name: string;
  lang: string;
  url: string;
  embedded: boolean;
  kind: SubtitleKind;
  codec: string;
  unsupported: boolean;
  unsupportedReason: string;
  forced: boolean;
  vttContent: string;      // 未加载时为空串
  blobUrl: string;         // 未加载时为空串
  loading: boolean;
  loadFailed: boolean;
}

interface AudioTrackData {
  index: number;
  label: string;
  lang: string;
}

interface VideoPlayerProps {
  path: string | null;
  onClose: () => void;
}

export function VideoPlayer({ path, onClose }: VideoPlayerProps) {
  const [error, setError] = useState<string | null>(null);
  const [subtitles, setSubtitles] = useState<SubtitleData[]>([]);
  const [activeSubIdx, setActiveSubIdx] = useState(0);
  const [subtitleNotice, setSubtitleNotice] = useState<string | null>(null);
  // 用户主动关掉提示后不再弹，避免"正在提取""图形字幕"这类信息一直挡着画面。
  // 只影响显示，后台提取照常进行。
  const [noticeDismissed, setNoticeDismissed] = useState(false);
  const [audioTracks, setAudioTracks] = useState<AudioTrackData[]>([]);
  const [activeAudioIdx, setActiveAudioIdx] = useState(0);
  const [isTranscode, setIsTranscode] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [seekOffset, setSeekOffset] = useState(0);
  const [buffering, setBuffering] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const blobUrlsRef = useRef<string[]>([]);
  // 供异步回调读取最新字幕状态。必须在设置状态的同时同步，
  // 不能只靠 useEffect —— "刚 setSubtitles 就要立刻取内容"的场景下
  // effect 还没跑，ref 里是空数组，取内容会被当成越界直接跳过。
  const subtitlesRef = useRef<SubtitleData[]>([]);
  const writeSubtitles = useCallback(
    (next: SubtitleData[] | ((prev: SubtitleData[]) => SubtitleData[])) => {
      const resolved = typeof next === "function"
        ? (next as (p: SubtitleData[]) => SubtitleData[])(subtitlesRef.current)
        : next;
      subtitlesRef.current = resolved;
      setSubtitles(resolved);
    },
    [],
  );

  const handleClose = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.removeAttribute("src");
      videoRef.current.load();
    }
    blobUrlsRef.current.forEach(url => URL.revokeObjectURL(url));
    blobUrlsRef.current = [];
    writeSubtitles([]);
    setSubtitleNotice(null);
    setNoticeDismissed(false);
    setAudioTracks([]);
    setActiveAudioIdx(0);
    setError(null);
    setDuration(0);
    setCurrentTime(0);
    setSeekOffset(0);
    setIsTranscode(false);
    onClose();
  }, [onClose]);

  const startPlayback = useCallback((videoPath: string, startTime: number = 0, audioIndex: number = 0) => {
    const video = videoRef.current;
    if (!video) return;

    const ext = videoPath.split(".").pop()?.toLowerCase() || "";
    const canPlayNatively = ["mp4", "m4v", "webm", "mov"].includes(ext);
    const unsupported = ["rmvb", "rm"];

    if (unsupported.includes(ext)) {
      setError(`${ext.toUpperCase()} 格式暂不支持浏览器播放，请使用本地播放器`);
      return;
    }

    setIsTranscode(!canPlayNatively);
    setError(null);
    setBuffering(true);

    if (canPlayNatively) {
      const streamUrl = `${BASE_URL}/playback/stream?path=${encodeURIComponent(videoPath)}`;
      video.src = streamUrl;
      video.load();
      if (startTime > 0) video.currentTime = startTime;
      video.play().catch(() => {});
    } else {
      const streamUrl = `${BASE_URL}/playback/transcode?path=${encodeURIComponent(videoPath)}&start=${startTime}&audio_index=${audioIndex}`;
      video.src = streamUrl;
      video.load();
      video.play().catch(() => {});
      setSeekOffset(startTime);
    }
  }, []);

  // 拉取某条字幕的 VTT 内容，成功后写回该轨的 vttContent/blobUrl。
  //
  // 判定必须走 ref 而不是在 setState updater 里给外部变量赋值：
  // React 会重复调用 updater（严格模式 / 并发渲染），第二次拿到的是
  // 已被标记 loading 的对象，据此判断就会直接 return，fetch 永远不发，
  // UI 卡在"提取中"。inFlightRef 单独记在途请求，去重不依赖渲染状态。
  const inFlightRef = useRef<Set<number>>(new Set());

  const fetchSubtitleContent = useCallback(async (idx: number) => {
    const target = subtitlesRef.current[idx];
    if (!target || target.unsupported) return;
    if (target.vttContent) return;              // 已有内容
    if (inFlightRef.current.has(idx)) return;   // 已在拉取

    inFlightRef.current.add(idx);
    writeSubtitles(prev => {
      if (!prev[idx]) return prev;
      const next = [...prev];
      next[idx] = { ...next[idx], loading: true, loadFailed: false };
      return next;
    });

    const url = target.url.startsWith("http") ? target.url : `${BASE_URL}${target.url}`;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const vttContent = await res.text();
      if (!vttContent.trim() || !vttContent.includes("-->")) {
        throw new Error("字幕内容为空");
      }
      const blobUrl = URL.createObjectURL(new Blob([vttContent], { type: "text/vtt" }));
      blobUrlsRef.current.push(blobUrl);
      writeSubtitles(prev => {
        const next = [...prev];
        if (next[idx]) next[idx] = { ...next[idx], vttContent, blobUrl, loading: false };
        return next;
      });
      setSubtitleNotice(null);
    } catch (e) {
      writeSubtitles(prev => {
        const next = [...prev];
        if (next[idx]) next[idx] = { ...next[idx], loading: false, loadFailed: true };
        return next;
      });
      const name = target.name || `字幕 ${idx + 1}`;
      setSubtitleNotice(
        target.embedded
          ? `「${name}」提取失败，大文件首次提取较慢，可稍后重试`
          : `「${name}」加载失败`
      );
    } finally {
      inFlightRef.current.delete(idx);
    }
  }, []);

  // 加载字幕列表：只拉元信息。外挂字幕直接读文件很快，立即加载；
  // 内嵌字幕要全量 demux，等用户选中才提取。
  const loadSubtitles = useCallback(async (videoPath: string) => {
    try {
      const res = await fetch(`${BASE_URL}/playback/subtitles?path=${encodeURIComponent(videoPath)}`);
      if (!res.ok) {
        setSubtitleNotice("字幕列表获取失败");
        return;
      }
      const data = await res.json();
      const tracks = data?.subtitles || [];

      const list: SubtitleData[] = tracks.map((t: any) => ({
        name: t.name || "",
        lang: t.lang || "",
        url: t.url || "",
        embedded: !!t.embedded,
        kind: (t.kind || (t.embedded ? "embedded" : "external")) as SubtitleKind,
        codec: t.codec || "",
        unsupported: !!t.unsupported,
        unsupportedReason: t.unsupported_reason || "",
        forced: !!t.forced,
        vttContent: "",
        blobUrl: "",
        loading: false,
        loadFailed: false,
      }));
      writeSubtitles(list);

      const summary = data?.summary;
      if (list.length === 0) {
        // 一条流都没有：字幕很可能被压进画面，检测不到也无法关闭
        setSubtitleNotice(
          summary?.maybe_hardcoded
            ? "未检测到字幕轨，若画面上有字幕则是压制进画面的硬字幕，无法开关"
            : null
        );
        setActiveSubIdx(-1);
        return;
      }

      const usable = list.filter(s => !s.unsupported);
      if (usable.length === 0) {
        const graphic = list.filter(s => s.kind === "graphic").length;
        setSubtitleNotice(
          graphic > 0
            ? `检测到 ${graphic} 条图形字幕（PGS/VobSub），是图片不是文本，浏览器无法渲染`
            : `检测到 ${list.length} 条字幕但格式不支持`
        );
        setActiveSubIdx(-1);
        return;
      }

      // 默认选中：优先中文外挂 → 中文内嵌 → 任意外挂 → 第一条可用
      const score = (s: SubtitleData) =>
        (s.lang === "zh" ? 2 : 0) + (s.embedded ? 0 : 1);
      let bestIdx = -1;
      let bestScore = -1;
      list.forEach((s, i) => {
        if (s.unsupported) return;
        const sc = score(s);
        if (sc > bestScore) { bestScore = sc; bestIdx = i; }
      });
      setActiveSubIdx(bestIdx);
      if (bestIdx >= 0) fetchSubtitleContent(bestIdx);

      // 内嵌字幕一并预加载，不等用户选中。
      // 后端一次 ffmpeg 调用会提取该文件全部文本轨并落盘，所以触发任意一条
      // 就等于暖好整个缓存，之后切轨/拖进度条都能立刻拿到字幕。
      // 按需加载虽然省一次提取，但用户切轨时要干等几十秒，体验更差。
      const firstEmbedded = list.findIndex(s => s.embedded && !s.unsupported);
      if (firstEmbedded >= 0 && firstEmbedded !== bestIdx) {
        void fetchSubtitleContent(firstEmbedded);
      }
    } catch {
      setSubtitleNotice("字幕列表获取失败");
    }
  }, [fetchSubtitleContent]);

  // 初始化
  useEffect(() => {
    if (!path) return;
    setError(null);
    setDuration(0);
    setCurrentTime(0);
    setSeekOffset(0);
    blobUrlsRef.current.forEach(url => URL.revokeObjectURL(url));
    blobUrlsRef.current = [];
    writeSubtitles([]);
    setSubtitleNotice(null);
    setNoticeDismissed(false);   // 换片子要重新允许提示
    setActiveSubIdx(0);
    setAudioTracks([]);
    setActiveAudioIdx(0);

    fetch(`${BASE_URL}/playback/duration?path=${encodeURIComponent(path)}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.duration) setDuration(data.duration); })
      .catch(() => {});

    // 加载音轨列表
    fetch(`${BASE_URL}/playback/audio-tracks?path=${encodeURIComponent(path)}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.tracks && data.tracks.length > 0) {
          setAudioTracks(data.tracks.map((t: any) => ({ index: t.index, label: t.label, lang: t.lang })));
        }
      })
      .catch(() => {});

    startPlayback(path, 0, 0);
    loadSubtitles(path);
  }, [path, startPlayback, loadSubtitles]);

  // 时间更新：转码模式用 requestVideoFrameCallback 精确跟踪实际渲染帧时间，
  // 避免"画面等音频对齐"期间字幕提前显示
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // 两条路径都用帧回调：字幕改成自绘后，timeupdate 每秒只触发约 4 次，
    // 字幕出现/消失会有肉眼可见的滞后。
    let frameCallbackId: number | null = null;
    const useFrameCallback = "requestVideoFrameCallback" in HTMLVideoElement.prototype;

    const onFrame = (_now: number, metadata: { mediaTime: number }) => {
      // 取 mediaTime 与 currentTime 的较小值。
      //
      // mediaTime 是"即将呈现的帧"的时间戳，会超前于实际听到的音频位置，
      // 直接用它算字幕时间会导致字幕提前出现。commit 681f5f7
      // 「SRT时间轴精度修正(min约束)」就是为此加的约束，别再删。
      //
      // 这和 seekOffset 是两个独立问题：seekOffset 修的是 seek 落点偏移，
      // 这里的 min 修的是同一时刻视频帧 PTS 与音频播放位置的差。
      const effectiveTime = Math.min(metadata.mediaTime, video.currentTime);
      setCurrentTime(seekOffset + effectiveTime);
      setBuffering(false);
      frameCallbackId = (video as any).requestVideoFrameCallback(onFrame);
    };

    const onTimeUpdate = () => {
      // 只在浏览器不支持帧回调时兜底。mp4 路径 seekOffset 恒为 0，
      // 转码路径才是真实落点，两者用同一个公式。
      if (!useFrameCallback) {
        setCurrentTime(seekOffset + video.currentTime);
      }
    };
    const onPlaying = () => setBuffering(false);
    const onWaiting = () => setBuffering(true);
    const onCanPlay = () => setBuffering(false);
    const onLoadedMetadata = () => {
      if (video.duration && isFinite(video.duration) && video.duration > 0) {
        setDuration(prev => prev > 0 ? prev : video.duration);
      }
    };
    const onError = () => {
      if (video.error) setError(`播放失败: ${video.error.message || "格式不支持"}`);
      setBuffering(false);
    };

    if (useFrameCallback) {
      frameCallbackId = (video as any).requestVideoFrameCallback(onFrame);
    }
    video.addEventListener("timeupdate", onTimeUpdate);
    video.addEventListener("playing", onPlaying);
    video.addEventListener("waiting", onWaiting);
    video.addEventListener("canplay", onCanPlay);
    video.addEventListener("loadedmetadata", onLoadedMetadata);
    video.addEventListener("error", onError);

    return () => {
      if (frameCallbackId !== null && useFrameCallback) {
        (video as any).cancelVideoFrameCallback(frameCallbackId);
      }
      video.removeEventListener("timeupdate", onTimeUpdate);
      video.removeEventListener("playing", onPlaying);
      video.removeEventListener("waiting", onWaiting);
      video.removeEventListener("canplay", onCanPlay);
      video.removeEventListener("loadedmetadata", onLoadedMetadata);
      video.removeEventListener("error", onError);
    };
  }, [seekOffset, isTranscode]);

  // 两条路径的字幕都由 SubtitleOverlay 自绘，这里只负责清掉可能残留的
  // 原生 track，避免浏览器同时渲染一份 ::cue 造成双重字幕。
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.querySelectorAll("track").forEach(t => t.remove());
    for (let k = 0; k < video.textTracks.length; k++) {
      video.textTracks[k].mode = "disabled";
    }
  }, [subtitles, isTranscode]);

  // 查 ffmpeg 用 -ss time 实际会落到的关键帧位置。
  // ffmpeg 会 snap 到 <= time 的最近关键帧（实测偏 1.4-5.3s，GOP 长的可达 10s），
  // 必须用这个真实值同时作为 start 参数和字幕 offset，否则字幕整体错位。
  const resolveKeyframe = useCallback(async (videoPath: string, time: number): Promise<number> => {
    if (time <= 0) return 0;
    try {
      const res = await fetch(
        `${BASE_URL}/playback/keyframe-time?path=${encodeURIComponent(videoPath)}&time=${time}`
      );
      if (!res.ok) return time;
      const data = await res.json();
      const actual = Number(data?.actual_start);
      return Number.isFinite(actual) ? actual : time;
    } catch {
      return time;   // 查询失败就用请求值，退化成旧行为而不是卡住
    }
  }, []);

  // 转码流 seek：换 URL 重启转码。用 seekSeqRef 丢弃过期响应，
  // 避免快速连续 seek 时旧的关键帧查询回来把 offset 覆盖成错的。
  const seekSeqRef = useRef(0);

  const handleSeek = useCallback(async (time: number) => {
    if (!path || !isTranscode) return;
    const video = videoRef.current;
    if (!video) return;

    const seq = ++seekSeqRef.current;
    video.pause();
    setBuffering(true);
    setCurrentTime(time);   // 先按用户意图更新进度条，避免手感迟滞

    // 查转码流的真实起点。start 参数仍传用户请求的 time —— 后端 output seek
    // 会自己落到 >= time 的关键帧，这里查出来的只是用来对齐字幕时间轴。
    const actualStart = await resolveKeyframe(path, time);
    if (seq !== seekSeqRef.current) return;   // 期间又 seek 了，丢弃这次

    setSeekOffset(actualStart);
    setCurrentTime(actualStart);

    const streamUrl = `${BASE_URL}/playback/transcode?path=${encodeURIComponent(path)}&start=${time}&audio_index=${activeAudioIdx}`;
    video.src = streamUrl;
    video.load();
    video.play().catch(() => {});
  }, [path, isTranscode, activeAudioIdx, resolveKeyframe]);

  // 音轨切换
  const handleAudioChange = useCallback((index: number) => {
    if (!path) return;
    setActiveAudioIdx(index);
    const video = videoRef.current;
    if (!video) return;

    if (!isTranscode) {
      // mp4 原生模式：先尝试浏览器 audioTracks API（Safari 支持）
      const tracks = (video as any).audioTracks;
      if (tracks && tracks.length > 1) {
        for (let i = 0; i < tracks.length; i++) {
          tracks[i].enabled = (i === index);
        }
        return;
      }
      // Chrome 等不支持 audioTracks API：用后端 remux + 原生播放器
      const currentPos = video.currentTime;
      const streamUrl = `${BASE_URL}/playback/stream?path=${encodeURIComponent(path)}&audio_index=${index}`;
      video.src = streamUrl;
      video.load();
      video.currentTime = currentPos;
      video.play().catch(() => {});
      return;
    }

    // 转码模式：重新发起转码请求，保持当前进度。
    // 同样要对齐关键帧，否则切完音轨字幕就偏了。
    void (async () => {
      const seq = ++seekSeqRef.current;
      video.pause();
      setBuffering(true);
      const resumeAt = currentTime;
      const actualStart = await resolveKeyframe(path, resumeAt);
      if (seq !== seekSeqRef.current) return;

      setSeekOffset(actualStart);
      setCurrentTime(actualStart);

      const streamUrl = `${BASE_URL}/playback/transcode?path=${encodeURIComponent(path)}&start=${resumeAt}&audio_index=${index}`;
      video.src = streamUrl;
      video.load();
      video.play().catch(() => {});
    })();
  }, [path, isTranscode, currentTime, resolveKeyframe]);

  // 字幕切换：选中未加载的轨时才去提取
  const handleSubtitleChange = useCallback((index: number) => {
    setActiveSubIdx(index);
    setSubtitleNotice(null);
    if (index >= 0) fetchSubtitleContent(index);
  }, [fetchSubtitleContent]);

  if (!path) return null;

  // mkv 字幕内容（SubtitleOverlay 用）；未加载完时为空串，覆盖层自然不渲染
  const activeSub = activeSubIdx >= 0 && activeSubIdx < subtitles.length
    ? subtitles[activeSubIdx] : null;
  const activeVtt = activeSub ? activeSub.vttContent : "";
  const subtitleLoading = !!activeSub?.loading;
  // 只有内嵌字幕才慢（要全量 demux），外挂字幕就是读个文件，不该显示耗时警告
  const loadingIsEmbedded = !!activeSub?.loading && !!activeSub?.embedded;

  return (
    <div className="fixed inset-0 bg-black/90 flex items-center justify-center z-[100]" onClick={handleClose}>
      <div ref={containerRef} className="w-[90vw] max-w-[1200px] bg-black rounded-lg overflow-hidden relative flex flex-col" onClick={e => e.stopPropagation()}>
        {/* 关闭按钮 */}
        <button onClick={handleClose}
          className="absolute top-3 right-3 z-10 w-8 h-8 bg-black/60 hover:bg-black/80 rounded-full flex items-center justify-center text-white text-sm">
          ✕
        </button>
        {error && (
          <div className="absolute inset-0 flex items-center justify-center z-20">
            <p className="text-red-400 text-sm px-4 text-center">{error}</p>
          </div>
        )}
        {/* 字幕提示（提取失败 / 全是图形字幕 / 内嵌首次提取中）。
            可手动关掉：关掉只是不再打扰，后台提取继续跑完。 */}
        {!error && !noticeDismissed && (subtitleNotice || loadingIsEmbedded) && (
          <div className="absolute top-3 left-3 z-20 max-w-[70%]">
            <div className="flex items-start gap-2 bg-black/70 rounded px-2.5 py-1.5">
              <p className="text-[11px] text-amber-300/90 leading-snug">
                {loadingIsEmbedded
                  ? "正在提取内嵌字幕，大文件需要数十秒…"
                  : subtitleNotice}
              </p>
              <button
                onClick={() => setNoticeDismissed(true)}
                title="关闭提示（提取继续在后台进行）"
                className="text-slate-400 hover:text-white text-[13px] leading-none shrink-0 mt-px"
              >
                ✕
              </button>
            </div>
          </div>
        )}
        {/* 视频区域 */}
        <div className="flex-1 aspect-video relative">
          <video
            ref={videoRef}
            controls={!isTranscode}
            autoPlay
            crossOrigin="anonymous"
            className="w-full h-full"
          />
          {/* 字幕统一自绘：原生 ::cue 的字号由浏览器按视频高度缩放、
              还会被用户的浏览器字幕设置覆盖，两条路径没法对齐。
              mp4 用原生 controls，字幕要抬高一点避免被控件挡住。 */}
          <SubtitleOverlay
            vttContent={activeVtt}
            currentTime={currentTime}
            visible={activeSubIdx >= 0}
            videoRef={videoRef}
            bottomOffset={isTranscode ? 16 : 56}
          />
          {/* mp4 原生 controls 里没有我们的字幕菜单，单独给一个入口 */}
          {!isTranscode && subtitles.length > 0 && (
            <SubtitlePicker
              subtitles={subtitles}
              activeIndex={activeSubIdx}
              onChange={handleSubtitleChange}
            />
          )}
        </div>
        {/* mkv 专用：自制控制栏 */}
        {isTranscode && (
          <TranscodeProgressBar
            currentTime={currentTime}
            duration={duration}
            buffering={buffering}
            onSeek={handleSeek}
            videoRef={videoRef}
            containerRef={containerRef}
            subtitles={subtitles.map((s, i) => ({
              name: s.name, lang: s.lang, index: i, kind: s.kind, forced: s.forced,
              unsupported: s.unsupported, unsupportedReason: s.unsupportedReason,
              loading: s.loading, loadFailed: s.loadFailed,
            }))}
            activeSubtitleIndex={activeSubIdx}
            onSubtitleChange={handleSubtitleChange}
            subtitleLoading={subtitleLoading}
            audioTracks={audioTracks}
            activeAudioIndex={activeAudioIdx}
            onAudioChange={handleAudioChange}
          />
        )}
        {/* mp4 原生模式：多音轨时显示音轨选择栏 */}
        {!isTranscode && audioTracks.length > 1 && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-black/60">
            <span className="text-[11px] text-slate-500">音轨:</span>
            {audioTracks.map((track) => (
              <button key={track.index} onClick={() => handleAudioChange(track.index)}
                className={`text-[11px] px-2 py-0.5 rounded truncate max-w-[200px] ${activeAudioIdx === track.index ? "bg-blue-500/20 text-blue-400" : "text-slate-400 hover:text-white"}`}>
                {track.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
