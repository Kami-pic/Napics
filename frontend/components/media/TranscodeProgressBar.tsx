// 转码流专用控制栏：播放/暂停 + 进度条 + 音量 + 字幕选择 + 全屏
"use client";
import { useState, useRef, useCallback, useEffect } from "react";

interface SubtitleInfo {
  name: string;
  lang: string;
  index: number;
  unsupported?: boolean;   // 图形字幕等无法渲染的轨
  loading?: boolean;       // 正在提取
  loadFailed?: boolean;    // 提取失败
}

interface AudioTrackInfo {
  label: string;
  lang: string;
  index: number;
}

interface TranscodeProgressBarProps {
  currentTime: number;
  duration: number;
  buffering: boolean;
  onSeek: (time: number) => void | Promise<void>;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  containerRef: React.RefObject<HTMLDivElement | null>;
  subtitles?: SubtitleInfo[];
  activeSubtitleIndex?: number;
  onSubtitleChange?: (index: number) => void;
  subtitleLoading?: boolean;
  audioTracks?: AudioTrackInfo[];
  activeAudioIndex?: number;
  onAudioChange?: (index: number) => void;
}

export function TranscodeProgressBar({
  currentTime, duration, buffering, onSeek, videoRef, containerRef,
  subtitles = [], activeSubtitleIndex = 0, onSubtitleChange, subtitleLoading = false,
  audioTracks = [], activeAudioIndex = 0, onAudioChange,
}: TranscodeProgressBarProps) {
  const barRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);
  const [hoverPos, setHoverPos] = useState<number | null>(null);
  const [paused, setPaused] = useState(false);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showSubMenu, setShowSubMenu] = useState(false);
  const [showAudioMenu, setShowAudioMenu] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const onPause = () => setPaused(true);
    const onPlay = () => setPaused(false);
    const onVol = () => { setVolume(video.volume); setMuted(video.muted); };
    video.addEventListener("pause", onPause);
    video.addEventListener("play", onPlay);
    video.addEventListener("volumechange", onVol);
    return () => {
      video.removeEventListener("pause", onPause);
      video.removeEventListener("play", onPlay);
      video.removeEventListener("volumechange", onVol);
    };
  }, [videoRef]);

  useEffect(() => {
    const onChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  const togglePlay = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) video.play().catch(() => {});
    else video.pause();
  }, [videoRef]);

  const toggleMute = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    video.muted = !video.muted;
  }, [videoRef]);

  const handleVolumeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const video = videoRef.current;
    if (!video) return;
    const v = parseFloat(e.target.value);
    video.volume = v;
    video.muted = v === 0;
  }, [videoRef]);

  const toggleFullscreen = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else container.requestFullscreen().catch(() => {});
  }, [containerRef]);

  const calcTime = useCallback((clientX: number) => {
    const bar = barRef.current;
    if (!bar || duration <= 0) return 0;
    const rect = bar.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    return ratio * duration;
  }, [duration]);

  // 拖拽期间只更新本地预览位置，松手才真正 seek。
  // 每次 seek 都要重启一路 ffmpeg，按 mousemove 触发的话拖一下就能拉起几十个进程。
  const [dragPreview, setDragPreview] = useState<number | null>(null);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (duration <= 0) return;
    setDragging(true);
    setDragPreview(calcTime(e.clientX));
  }, [calcTime, duration]);

  useEffect(() => {
    if (!dragging) return;
    const handleMove = (e: MouseEvent) => setDragPreview(calcTime(e.clientX));
    const handleUp = (e: MouseEvent) => {
      setDragging(false);
      const target = calcTime(e.clientX);
      setDragPreview(null);
      onSeek(target);
    };
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [dragging, calcTime, onSeek]);

  // 点击外部关闭字幕菜单
  useEffect(() => {
    if (!showSubMenu) return;
    const close = () => setShowSubMenu(false);
    const timer = setTimeout(() => document.addEventListener("click", close), 50);
    return () => { clearTimeout(timer); document.removeEventListener("click", close); };
  }, [showSubMenu]);

  // 点击外部关闭音轨菜单
  useEffect(() => {
    if (!showAudioMenu) return;
    const close = () => setShowAudioMenu(false);
    const timer = setTimeout(() => document.addEventListener("click", close), 50);
    return () => { clearTimeout(timer); document.removeEventListener("click", close); };
  }, [showAudioMenu]);

  // 拖拽中显示预览位置，松手后回到真实播放位置
  const displayTime = dragPreview !== null ? dragPreview : currentTime;
  const progress = duration > 0 ? (displayTime / duration) * 100 : 0;
  const hoverProgress = hoverPos !== null && duration > 0 ? (hoverPos / duration) * 100 : null;
  const canSeek = duration > 0;

  return (
    <div className="flex items-center gap-1.5 px-3 py-2 bg-black/80 select-none relative">
      {/* 播放/暂停 */}
      <button onClick={togglePlay} className="w-7 h-7 flex items-center justify-center text-white hover:text-blue-400 transition-colors flex-shrink-0">
        {paused ? (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
        ) : (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" /></svg>
        )}
      </button>

      {/* 时间（拖拽中显示目标位置） */}
      <span className={`text-[11px] tabular-nums flex-shrink-0 ${dragPreview !== null ? "text-blue-400" : "text-slate-400"}`}>
        {formatTime(displayTime)}
      </span>

      {/* 进度条 */}
      <div
        ref={barRef}
        className={`flex-1 h-[6px] bg-white/10 rounded-full relative group ${canSeek ? "cursor-pointer" : "cursor-default opacity-50"}`}
        onMouseDown={handleMouseDown}
        onMouseMove={e => { if (canSeek) setHoverPos(calcTime(e.clientX)); }}
        onMouseLeave={() => setHoverPos(null)}
      >
        <div className="absolute inset-y-0 left-0 bg-blue-500 rounded-full transition-[width] duration-100" style={{ width: `${Math.min(100, progress)}%` }} />
        {hoverProgress !== null && <div className="absolute inset-y-0 left-0 bg-white/20 rounded-full pointer-events-none" style={{ width: `${hoverProgress}%` }} />}
        {canSeek && <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-blue-400 rounded-full shadow opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" style={{ left: `${Math.min(100, progress)}%`, marginLeft: "-6px" }} />}
      </div>

      {/* 总时长 */}
      <span className="text-[11px] text-slate-400 tabular-nums flex-shrink-0">
        {duration > 0 ? formatTime(duration) : "--:--"}
      </span>

      {/* 音量 */}
      <button onClick={toggleMute} className="w-6 h-6 flex items-center justify-center text-slate-400 hover:text-white transition-colors flex-shrink-0">
        {muted || volume === 0 ? (
          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" /></svg>
        ) : (
          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" /></svg>
        )}
      </button>
      <input type="range" min="0" max="1" step="0.05" value={muted ? 0 : volume} onChange={handleVolumeChange} className="w-14 h-1 accent-blue-500 cursor-pointer flex-shrink-0" />

      {/* 字幕选择 */}
      {subtitles.length > 0 && (
        <div className="relative flex-shrink-0">
          <button onClick={e => { e.stopPropagation(); setShowSubMenu(!showSubMenu); setShowAudioMenu(false); }}
            className={`w-7 h-7 flex items-center justify-center transition-colors flex-shrink-0 ${
              subtitleLoading ? "text-amber-400 animate-pulse"
                : activeSubtitleIndex >= 0 ? "text-blue-400" : "text-slate-400 hover:text-white"
            }`}
            title={subtitleLoading ? "正在提取字幕…" : "字幕"}>
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M19 4H5c-1.11 0-2 .9-2 2v12c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm-8 7H9.5v-.5h-2v3h2V13H11v1c0 .55-.45 1-1 1H7c-.55 0-1-.45-1-1v-4c0-.55.45-1 1-1h3c.55 0 1 .45 1 1v1zm7 0h-1.5v-.5h-2v3h2V13H18v1c0 .55-.45 1-1 1h-3c-.55 0-1-.45-1-1v-4c0-.55.45-1 1-1h3c.55 0 1 .45 1 1v1z" /></svg>
          </button>
          {showSubMenu && (
            <div className="absolute bottom-full right-0 mb-2 bg-[#1a1a1a] border border-white/10 rounded-lg shadow-xl py-1 min-w-[180px] z-50" onClick={e => e.stopPropagation()}>
              <div className="px-3 py-1.5 text-[10px] text-slate-500 uppercase tracking-wider">字幕轨道</div>
              {/* 关闭字幕选项 */}
              <button
                onClick={() => { onSubtitleChange?.(-1); setShowSubMenu(false); }}
                className={`w-full text-left px-3 py-1.5 text-xs hover:bg-white/5 transition-colors ${activeSubtitleIndex === -1 ? "text-blue-400" : "text-slate-300"}`}>
                关闭字幕
              </button>
              {subtitles.map((sub) => {
                const disabled = !!sub.unsupported;
                const cls = disabled
                  ? "text-slate-600 cursor-not-allowed"
                  : activeSubtitleIndex === sub.index ? "text-blue-400" : "text-slate-300 hover:bg-white/5";
                return (
                  <button key={sub.index}
                    disabled={disabled}
                    title={disabled ? sub.name : undefined}
                    onClick={() => {
                      if (disabled) return;
                      onSubtitleChange?.(sub.index);
                      setShowSubMenu(false);
                    }}
                    className={`w-full text-left px-3 py-1.5 text-xs transition-colors truncate ${cls}`}>
                    {sub.name}
                    {sub.loading && <span className="text-amber-400"> · 提取中</span>}
                    {sub.loadFailed && <span className="text-red-400"> · 失败</span>}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 音轨选择 */}
      {audioTracks.length > 1 && (
        <div className="relative flex-shrink-0">
          <button onClick={e => { e.stopPropagation(); setShowAudioMenu(!showAudioMenu); setShowSubMenu(false); }}
            className="w-7 h-7 flex items-center justify-center text-slate-400 hover:text-white transition-colors flex-shrink-0"
            title="音轨">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 3v9.28c-.47-.17-.97-.28-1.5-.28C8.01 12 6 14.01 6 16.5S8.01 21 10.5 21c2.31 0 4.2-1.75 4.45-4H15V6h4V3h-7z" /></svg>
          </button>
          {showAudioMenu && (
            <div className="absolute bottom-full right-0 mb-2 bg-[#1a1a1a] border border-white/10 rounded-lg shadow-xl py-1 min-w-[180px] z-50" onClick={e => e.stopPropagation()}>
              <div className="px-3 py-1.5 text-[10px] text-slate-500 uppercase tracking-wider">音轨</div>
              {audioTracks.map((track) => (
                <button key={track.index}
                  onClick={() => { onAudioChange?.(track.index); setShowAudioMenu(false); }}
                  className={`w-full text-left px-3 py-1.5 text-xs hover:bg-white/5 transition-colors truncate ${activeAudioIndex === track.index ? "text-blue-400" : "text-slate-300"}`}>
                  {track.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 全屏 */}
      <button onClick={toggleFullscreen} className="w-7 h-7 flex items-center justify-center text-slate-400 hover:text-white transition-colors flex-shrink-0">
        {isFullscreen ? (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z" /></svg>
        ) : (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z" /></svg>
        )}
      </button>

      {/* 缓冲 */}
      {buffering && <span className="text-[10px] text-yellow-400 animate-pulse flex-shrink-0">缓冲中</span>}
    </div>
  );
}

function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return "0:00";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  return `${m}:${s.toString().padStart(2, "0")}`;
}
