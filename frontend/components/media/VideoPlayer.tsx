// 全局视频播放器弹窗
// mp4/webm：原生 controls + Blob URL <track> 字幕（浏览器内置 CC 按钮）
// mkv/ts/avi：自制控制栏 + SubtitleOverlay 覆盖层渲染字幕
"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { BASE_URL } from "@/lib/api/base";
import { TranscodeProgressBar } from "./TranscodeProgressBar";
import { SubtitleOverlay } from "./SubtitleOverlay";

interface SubtitleData {
  name: string;
  lang: string;
  vttContent: string;
  blobUrl: string;
}

interface VideoPlayerProps {
  path: string | null;
  onClose: () => void;
}

export function VideoPlayer({ path, onClose }: VideoPlayerProps) {
  const [error, setError] = useState<string | null>(null);
  const [subtitles, setSubtitles] = useState<SubtitleData[]>([]);
  const [activeSubIdx, setActiveSubIdx] = useState(0);
  const [isTranscode, setIsTranscode] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [seekOffset, setSeekOffset] = useState(0);
  const [buffering, setBuffering] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const blobUrlsRef = useRef<string[]>([]);

  const handleClose = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.removeAttribute("src");
      videoRef.current.load();
    }
    blobUrlsRef.current.forEach(url => URL.revokeObjectURL(url));
    blobUrlsRef.current = [];
    setSubtitles([]);
    setError(null);
    setDuration(0);
    setCurrentTime(0);
    setSeekOffset(0);
    setIsTranscode(false);
    onClose();
  }, [onClose]);

  const startPlayback = useCallback((videoPath: string, startTime: number = 0) => {
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
      const streamUrl = `${BASE_URL}/playback/transcode?path=${encodeURIComponent(videoPath)}&start=${startTime}`;
      video.src = streamUrl;
      video.load();
      video.play().catch(() => {});
      setSeekOffset(startTime);
    }
  }, []);

  // 加载字幕：fetch VTT 内容 + 创建 Blob URL
  const loadSubtitles = useCallback(async (videoPath: string) => {
    try {
      const res = await fetch(`${BASE_URL}/playback/subtitles?path=${encodeURIComponent(videoPath)}`);
      if (!res.ok) return;
      const data = await res.json();
      const tracks = data?.subtitles || [];
      if (tracks.length === 0) return;

      const loaded: SubtitleData[] = [];
      for (const track of tracks) {
        const subtitleUrl = track.url.startsWith("http") ? track.url : `${BASE_URL}${track.url}`;
        try {
          const subRes = await fetch(subtitleUrl);
          if (!subRes.ok) continue;
          const vttContent = await subRes.text();
          const blob = new Blob([vttContent], { type: "text/vtt" });
          const blobUrl = URL.createObjectURL(blob);
          blobUrlsRef.current.push(blobUrl);
          loaded.push({ name: track.name, lang: track.lang, vttContent, blobUrl });
        } catch { /* 单条失败不影响 */ }
      }
      if (loaded.length > 0) {
        setSubtitles(loaded);
        setActiveSubIdx(0);
      }
    } catch { /* 字幕加载失败不影响播放 */ }
  }, []);

  // 初始化
  useEffect(() => {
    if (!path) return;
    setError(null);
    setDuration(0);
    setCurrentTime(0);
    setSeekOffset(0);
    blobUrlsRef.current.forEach(url => URL.revokeObjectURL(url));
    blobUrlsRef.current = [];
    setSubtitles([]);
    setActiveSubIdx(0);

    fetch(`${BASE_URL}/playback/duration?path=${encodeURIComponent(path)}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.duration) setDuration(data.duration); })
      .catch(() => {});

    startPlayback(path, 0);
    loadSubtitles(path);
  }, [path, startPlayback, loadSubtitles]);

  // 时间更新
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const onTimeUpdate = () => {
      if (isTranscode) {
        setCurrentTime(seekOffset + video.currentTime);
      } else {
        setCurrentTime(video.currentTime);
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

    video.addEventListener("timeupdate", onTimeUpdate);
    video.addEventListener("playing", onPlaying);
    video.addEventListener("waiting", onWaiting);
    video.addEventListener("canplay", onCanPlay);
    video.addEventListener("loadedmetadata", onLoadedMetadata);
    video.addEventListener("error", onError);

    return () => {
      video.removeEventListener("timeupdate", onTimeUpdate);
      video.removeEventListener("playing", onPlaying);
      video.removeEventListener("waiting", onWaiting);
      video.removeEventListener("canplay", onCanPlay);
      video.removeEventListener("loadedmetadata", onLoadedMetadata);
      video.removeEventListener("error", onError);
    };
  }, [seekOffset, isTranscode]);

  // mp4 原生播放器：字幕通过 Blob URL <track> 标签，浏览器原生 CC 按钮选择
  // 在 subtitles 加载完后注入 track 元素并激活
  useEffect(() => {
    if (isTranscode) return; // mkv 用 SubtitleOverlay，不走这里
    const video = videoRef.current;
    if (!video || subtitles.length === 0) return;

    // 注入 track 元素
    video.querySelectorAll("track").forEach(t => t.remove());
    subtitles.forEach((sub, i) => {
      const track = document.createElement("track");
      track.kind = "subtitles";
      track.label = sub.name || `字幕 ${i + 1}`;
      track.srclang = sub.lang || "zh";
      track.src = sub.blobUrl;
      if (i === 0) track.default = true;
      video.appendChild(track);
    });

    // 延迟激活第一条字幕轨
    const timer = setTimeout(() => {
      if (video.textTracks.length > 0) {
        video.textTracks[0].mode = "showing";
      }
    }, 800);
    return () => clearTimeout(timer);
  }, [subtitles, isTranscode]);

  // 转码流 seek
  const handleSeek = useCallback((time: number) => {
    if (!path || !isTranscode) return;
    const video = videoRef.current;
    if (!video) return;

    video.pause();
    setBuffering(true);
    setSeekOffset(time);
    setCurrentTime(time);

    const streamUrl = `${BASE_URL}/playback/transcode?path=${encodeURIComponent(path)}&start=${time}`;
    video.src = streamUrl;
    video.load();
    video.play().catch(() => {});
  }, [path, isTranscode]);

  // mkv 字幕切换
  const handleSubtitleChange = useCallback((index: number) => {
    setActiveSubIdx(index);
  }, []);

  if (!path) return null;

  // mkv 字幕内容（SubtitleOverlay 用）
  const activeVtt = isTranscode && activeSubIdx >= 0 && activeSubIdx < subtitles.length
    ? subtitles[activeSubIdx].vttContent : "";

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
        {/* 视频区域 */}
        <div className="flex-1 aspect-video relative">
          <video
            ref={videoRef}
            controls={!isTranscode}
            autoPlay
            crossOrigin="anonymous"
            className="w-full h-full"
          />
          {/* mkv 专用：SubtitleOverlay 覆盖层渲染字幕 */}
          {isTranscode && (
            <SubtitleOverlay vttContent={activeVtt} currentTime={currentTime} visible={activeSubIdx >= 0} />
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
            subtitles={subtitles.map((s, i) => ({ name: s.name, lang: s.lang, index: i }))}
            activeSubtitleIndex={activeSubIdx}
            onSubtitleChange={handleSubtitleChange}
          />
        )}
      </div>
    </div>
  );
}
