// mp4 原生 controls 模式下的字幕选择入口。
// 转码模式的字幕菜单在 TranscodeProgressBar 里，两者共用同一份字幕数据。
"use client";
import { useState, useEffect } from "react";

export interface SubtitlePickerTrack {
  name: string;
  lang: string;
  kind: "external" | "embedded" | "graphic";
  unsupported: boolean;
  unsupportedReason: string;
  forced: boolean;
  loading: boolean;
  loadFailed: boolean;
}

export interface SubtitlePickerProps {
  subtitles: SubtitlePickerTrack[];
  activeIndex: number;
  onChange: (index: number) => void;
}

const KIND_LABEL: Record<string, string> = {
  external: "外挂",
  embedded: "内嵌",
  graphic: "图形",
};

const KIND_STYLE: Record<string, string> = {
  external: "bg-emerald-500/15 text-emerald-400",
  embedded: "bg-blue-500/15 text-blue-400",
  graphic: "bg-slate-600/30 text-slate-500",
};

export function SubtitlePicker({ subtitles, activeIndex, onChange }: SubtitlePickerProps) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const timer = setTimeout(() => document.addEventListener("click", close), 50);
    return () => { clearTimeout(timer); document.removeEventListener("click", close); };
  }, [open]);

  const loading = subtitles.some(s => s.loading);

  return (
    <div className="absolute top-3 right-14 z-30" onClick={e => e.stopPropagation()}>
      <button
        onClick={() => setOpen(!open)}
        title={loading ? "正在提取字幕…" : "字幕"}
        className={`w-8 h-8 rounded-full bg-black/60 hover:bg-black/80 flex items-center justify-center transition-colors ${
          loading ? "text-amber-400 animate-pulse"
            : activeIndex >= 0 ? "text-blue-400" : "text-slate-300"
        }`}
      >
        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
          <path d="M19 4H5c-1.11 0-2 .9-2 2v12c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm-8 7H9.5v-.5h-2v3h2V13H11v1c0 .55-.45 1-1 1H7c-.55 0-1-.45-1-1v-4c0-.55.45-1 1-1h3c.55 0 1 .45 1 1v1zm7 0h-1.5v-.5h-2v3h2V13H18v1c0 .55-.45 1-1 1h-3c-.55 0-1-.45-1-1v-4c0-.55.45-1 1-1h3c.55 0 1 .45 1 1v1z" />
        </svg>
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-2 bg-[#1a1a1a] border border-white/10 rounded-lg shadow-xl py-1 min-w-[200px]">
          <div className="px-3 py-1.5 text-[10px] text-slate-500 uppercase tracking-wider">字幕轨道</div>
          <button
            onClick={() => { onChange(-1); setOpen(false); }}
            className={`w-full text-left px-3 py-1.5 text-xs hover:bg-white/5 transition-colors ${
              activeIndex === -1 ? "text-blue-400" : "text-slate-300"
            }`}
          >
            关闭字幕
          </button>
          {subtitles.map((sub, i) => {
            const disabled = sub.unsupported;
            const cls = disabled
              ? "text-slate-600 cursor-not-allowed"
              : activeIndex === i ? "text-blue-400" : "text-slate-300 hover:bg-white/5";
            return (
              <button
                key={i}
                disabled={disabled}
                title={disabled ? (sub.unsupportedReason || sub.name) : sub.name}
                onClick={() => { if (!disabled) { onChange(i); setOpen(false); } }}
                className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${cls}`}
              >
                <span className="flex items-center gap-1.5">
                  <span className={`text-[9px] px-1 py-px rounded shrink-0 ${KIND_STYLE[sub.kind] || ""}`}>
                    {KIND_LABEL[sub.kind] || sub.kind}
                  </span>
                  <span className="truncate">{sub.name}</span>
                  {sub.forced && <span className="text-[9px] text-orange-400 shrink-0">强制</span>}
                  {sub.loading && <span className="text-amber-400 shrink-0">提取中</span>}
                  {sub.loadFailed && <span className="text-red-400 shrink-0">失败</span>}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
