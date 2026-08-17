// 播放按钮：点击触发播放（由页面级 handlePlay 处理本地/浏览器回退逻辑）
"use client";

interface PlayButtonProps {
  filePath: string;
  onPlay: (path: string) => void;
}

export function PlayButton({ filePath, onPlay }: PlayButtonProps) {
  return (
    <button
      onClick={() => onPlay(filePath)}
      className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-medium flex items-center justify-center gap-1.5"
    >
      <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
      播放
    </button>
  );
}
