// 全局视频播放器弹窗：mp4/webm 直连播放，其他格式通过后端 ffmpeg 转码（支持 seek + 字幕）
"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { BASE_URL } from "@/lib/api/base";
import { TranscodeProgressBar } from "./TranscodeProgressBar";
import { SubtitleOverlay } from "./SubtitleOverlay";

interface SubtitleData {
  name: string;
  lang: string;
  vttContent: string;  // VTT 原文（用于 overlay 渲染）
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

  const handleClose = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.removeAttribute("src");
      videoRef.current.load();
    }
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

  // 加载字幕：fetch VTT 内容到内存（不依赖浏览器 track API）
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
          loaded.push({ name: track.name, lang: track.lang, vttContent });
        } catch { /* 单条失败不影响其他 */ }
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
    setSubtitles([]);
    setActiveSubIdx(0);

    fetch(`${BASE_URL}/playback/duration?path=${encodeURIComponent(path)}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.duration) setDuration(data.duration); })
      .catch(() => {});

    startPlayback(path, 0);
    loadSubtitles(path);
  }, [path, startPlayback, loadSubtitles]);

  // video 事件监听：只在视频帧实际渲染时更新 currentTime（避免缓冲期字幕超前）
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    let frameCallbackId: number | null = null;

    // 用 requestVideoFrameCallback 精确跟踪视频帧渲染时间
    const useFrameCallback = "requestVideoFrameCallback" in HTMLVideoElement.prototype;

    const onFrame = (_now: number, metadata: { mediaTime: number }) => {
      setCurrentTime(seekOffset + metadata.mediaTime);
      setBuffering(false);
      frameCallbackId = (video as any).requestVideoFrameCallback(onFrame);
    };

    // fallback：没有 requestVideoFrameCallback 时用 timeupdate
    const onTimeUpdate = () => {
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
    const onDurationChange = () => {
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
    video.addEventListener("durationchange", onDurationChange);
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
      video.removeEventListener("durationchange", onDurationChange);
      video.removeEventListener("error", onError);
    };
  }, [seekOffset]);

  // 转码流 seek
  const handleSeek = useCallback(async (time: number) => {
    if (!path || !isTranscode) return;
    const video = videoRef.current;
    if (!video) return;

    video.pause();
    setBuffering(true);
    setSeekOffset(time);
    setCurrentTime(time); // 冻结字幕在目标位置，等 requestVideoFrameCallback 更新

    const streamUrl = `${BASE_URL}/playback/transcode?path=${encodeURIComponent(path)}&start=${time}`;
    video.src = streamUrl;
    video.load();
    video.play().catch(() => {});
  }, [path, isTranscode]);

  // 字幕切换
  const handleSubtitleChange = useCallback((index: number) => {
    setActiveSubIdx(index);
  }, []);

  if (!path) return null;

  const activeVtt = (activeSubIdx >= 0 && activeSubIdx < subtitles.length) ? subtitles[activeSubIdx].vttContent : "";

  return (
    <div className="fixed inset-0 bg-black/90 flex items-center justify-center z-[100]" onClick={handleClose}>
      <div ref={containerRef} className="w-[90vw] max-w-[1200px] bg-black rounded-lg overflow-hidden relative flex flex-col" onClick={e => e.stopPropagation()}>
        {/* 关闭按钮 */}
        <button onClick={handleClose}
          className="absolute top-3 right-3 z-10 w-8 h-8 bg-black/60 hover:bg-black/80 rounded-full flex items-center justify-center text-white text-sm">
          ✕
        </button>
        {/* 错误提示 */}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center z-20">
            <p className="text-red-400 text-sm px-4 text-center">{error}</p>
          </div>
        )}
        {/* 视频区域 + 字幕覆盖 */}
        <div className="flex-1 aspect-video relative">
          <video
            ref={videoRef}
            controls={!isTranscode}
            autoPlay
            className="w-full h-full"
          />
          {/* 自渲染字幕覆盖层（不依赖浏览器 track API） */}
          <SubtitleOverlay
            vttContent={activeVtt}
            currentTime={currentTime}
            visible={activeSubIdx >= 0}
          />
        </div>
        {/* 转码流自定义控制栏 */}
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
