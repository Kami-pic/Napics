// 全局视频播放器弹窗：mp4/webm 直接播放，其他格式通过后端 ffmpeg 转码
"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { BASE_URL } from "@/lib/api/base";

interface SubtitleTrack {
  name: string;
  format: string;
  lang: string;
  url: string;
}

interface VideoPlayerProps {
  path: string | null;
  onClose: () => void;
}

export function VideoPlayer({ path, onClose }: VideoPlayerProps) {
  const [error, setError] = useState<string | null>(null);
  const [subtitles, setSubtitles] = useState<SubtitleTrack[]>([]);
  const videoRef = useRef<HTMLVideoElement>(null);

  const handleClose = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.removeAttribute("src");
      videoRef.current.load();
    }
    setSubtitles([]);
    setError(null);
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!path) return;
    const video = videoRef.current;
    if (!video) return;

    setError(null);
    const ext = path.split(".").pop()?.toLowerCase() || "";
    const canPlayNatively = ["mp4", "m4v", "webm", "mov"].includes(ext);
    const unsupported = ["rmvb", "rm"];

    if (unsupported.includes(ext)) {
      setError(`${ext.toUpperCase()} 格式暂不支持浏览器播放，请使用本地播放器`);
      return;
    }

    // mp4/webm 直接播放；mkv/ts/avi 等走后端 ffmpeg 转码流
    const streamUrl = canPlayNatively
      ? `${BASE_URL}/playback/stream?path=${encodeURIComponent(path)}`
      : `${BASE_URL}/playback/transcode?path=${encodeURIComponent(path)}`;

    video.src = streamUrl;
    video.load();
    video.play().catch(() => {});

    // 加载外挂字幕
    fetch(`${BASE_URL}/playback/subtitles?path=${encodeURIComponent(path)}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.subtitles?.length) {
          setSubtitles(data.subtitles.map((s: any) => ({ ...s, url: `${BASE_URL}${s.url}` })));
        }
      })
      .catch(() => {});

    const onError = () => {
      if (video.error) setError(`播放失败: ${video.error.message || "格式不支持"}`);
    };
    video.addEventListener("error", onError);
    return () => video.removeEventListener("error", onError);
  }, [path]);

  // 字幕加载到 video
  useEffect(() => {
    const video = videoRef.current;
    if (!video || subtitles.length === 0) return;
    while (video.querySelector("track")) video.removeChild(video.querySelector("track")!);
    subtitles.forEach((sub, i) => {
      const track = document.createElement("track");
      track.kind = "subtitles";
      track.label = sub.name || `字幕 ${i + 1}`;
      track.srclang = sub.lang || "zh";
      track.src = sub.url;
      if (i === 0) track.default = true;
      video.appendChild(track);
    });
    if (video.textTracks.length > 0) video.textTracks[0].mode = "showing";
  }, [subtitles]);

  if (!path) return null;

  return (
    <div className="fixed inset-0 bg-black/90 flex items-center justify-center z-[100]" onClick={handleClose}>
      <div className="w-[90vw] max-w-[1000px] aspect-video bg-black rounded-lg overflow-hidden relative" onClick={e => e.stopPropagation()}>
        <button onClick={handleClose}
          className="absolute top-3 right-3 z-10 w-8 h-8 bg-black/60 hover:bg-black/80 rounded-full flex items-center justify-center text-white text-sm">
          ✕
        </button>
        {error && (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-red-400 text-sm px-4 text-center">{error}</p>
          </div>
        )}
        <video ref={videoRef} controls autoPlay crossOrigin="anonymous" className="w-full h-full" />
      </div>
    </div>
  );
}
