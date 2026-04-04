"use client";
import { useState, useMemo } from "react";
import type { FolderNode, VideoInfo } from "@/types";
import { api } from "@/lib/api";
import { formatDuration } from "@/lib/utils";

interface TvDetailProps {
  node: FolderNode;
  onSelectEpisode: (video: VideoInfo) => void;
  onSeasonChange: (seasonNode: FolderNode | null) => void;
}

export default function TvDetail({ node, onSelectEpisode, onSeasonChange }: TvDetailProps) {
  // 提取季子目录
  const seasons = useMemo(() => {
    return node.children
      .filter(c => c.video_count > 0)
      .sort((a, b) => a.name.localeCompare(b.name, "zh-CN", { numeric: true }));
  }, [node.children]);

  const hasSeasons = seasons.length > 0;
  const [activeSeasonIdx, setActiveSeasonIdx] = useState(0);

  // 当前季的集列表
  const currentSeason = hasSeasons ? seasons[activeSeasonIdx] : null;
  const episodes = currentSeason ? currentSeason.videos : node.videos;

  const handleSeasonChange = (idx: number) => {
    setActiveSeasonIdx(idx);
    onSeasonChange(seasons[idx] || null);
  };

  return (
    <div className="space-y-3">
      {/* 季 tab（多季时显示） */}
      {hasSeasons && seasons.length > 1 && (
        <div className="flex gap-1.5 overflow-x-auto pb-1">
          {seasons.map((s, i) => (
            <button
              key={s.path}
              onClick={() => handleSeasonChange(i)}
              className={`px-3 py-1.5 rounded-md text-xs whitespace-nowrap transition-all flex-shrink-0 ${
                i === activeSeasonIdx
                  ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                  : "bg-white/[0.04] text-slate-500 hover:text-slate-300 border border-transparent"
              }`}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}

      {/* 单季标题 */}
      {hasSeasons && seasons.length === 1 && (
        <div className="text-xs text-slate-500 px-1">{seasons[0].name}</div>
      )}

      {/* 集列表 */}
      <div className="space-y-1">
        {episodes.map(ep => (
          <button
            key={ep.file_path}
            onClick={() => onSelectEpisode(ep)}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] text-left transition-all"
          >
            <span className="text-xs text-slate-400 truncate flex-1">{ep.file_name}</span>
            <div className="flex items-center gap-2 flex-shrink-0">
              {ep.resolution && <span className="text-[10px] text-slate-600">{ep.resolution}</span>}
              {ep.duration > 0 && <span className="text-[10px] text-slate-600">{formatDuration(ep.duration)}</span>}
            </div>
          </button>
        ))}
        {episodes.length === 0 && <p className="text-xs text-slate-600 py-4 text-center">暂无剧集</p>}
      </div>
    </div>
  );
}
