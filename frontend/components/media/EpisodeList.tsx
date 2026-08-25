// 剧集列表 — 从 CardGrid.tsx 拆分
"use client";
import { useMemo } from "react";
import type { VideoInfo } from "@/types";
import { formatSize, naturalCompare } from "@/lib/utils";

export default function EpisodeList({ videos, selectedPaths, onToggleSelect, onPlay, onSearch, onVideoDetail, batchMode, sortAsc = true }: {
  videos: VideoInfo[]; selectedPaths: Set<string>; onToggleSelect: (p: string) => void;
  onPlay: (p: string) => void; onSearch: (q: string, ctx?: { cnName?: string; enName?: string; originalName?: string }) => void; onVideoDetail: (v: VideoInfo) => void; batchMode?: boolean; sortAsc?: boolean;
}) {
  const sorted = useMemo(() => {
    const arr = [...videos];
    arr.sort((a, b) => naturalCompare(a.file_name, b.file_name));
    return sortAsc ? arr : arr.reverse();
  }, [videos, sortAsc]);

  return (
    <div className="space-y-1 overflow-y-auto no-scrollbar">
        {sorted.map((v, idx) => (
          <div key={v.file_path}
            className={`flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all cursor-pointer ${selectedPaths.has(v.file_path) ? "bg-blue-500/10" : "hover:bg-white/[0.03]"}`}
            onClick={() => onVideoDetail(v)}>
            {batchMode && (
              <input type="checkbox" checked={selectedPaths.has(v.file_path)} onChange={() => onToggleSelect(v.file_path)} onClick={e => e.stopPropagation()}
                className="w-4 h-4 rounded border-slate-600 bg-transparent checked:bg-blue-500 cursor-pointer flex-shrink-0" />
            )}
            <span className="text-xs text-slate-600 font-mono w-7 flex-shrink-0">{String(idx + 1).padStart(2, '0')}</span>
            <p className="text-[14px] text-slate-300 truncate flex-1 flex items-center gap-1.5">
              {!v.shadow_name && !v.organize_status && <span title="未整理" className="inline-block w-1.5 h-1.5 rounded-full bg-slate-500 flex-shrink-0" />}
              {v.organize_status === "scrape_failed" && <span title="识别失败" className="text-orange-400 text-xs flex-shrink-0">⚠</span>}
              {v.file_name}
            </p>
            <span className="text-xs text-slate-600 flex-shrink-0">{v.resolution}</span>
            <span className="text-xs text-slate-600 flex-shrink-0">{formatSize(v.size_gb)}</span>
            <button onClick={(e) => { e.stopPropagation(); onPlay(v.file_path); }} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all flex-shrink-0">
              <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
            </button>
            <button onClick={(e) => { e.stopPropagation(); onSearch(v.clean_name_cn || v.clean_name || v.file_name, { cnName: v.clean_name_cn, enName: v.clean_name_en, originalName: v.clean_name_original }); }} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-blue-400 hover:bg-blue-500/10 transition-all flex-shrink-0">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" /></svg>
            </button>
          </div>
        ))}
        {videos.length === 0 && <p className="text-sm text-slate-600 py-6 text-center">暂无视频文件</p>}
      </div>
  );
}
