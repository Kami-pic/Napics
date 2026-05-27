// 展开面板 — 从 CardGrid.tsx 拆分
"use client";
import { useState, useEffect } from "react";
import type { VideoInfo, FolderNode } from "@/types";
import { formatSize } from "@/lib/utils";
import CardPoster from "./CardPoster";
import EpisodeList from "./EpisodeList";
import { getSeasonLabel } from "./cardGridUtils";
import type { CardItem } from "./cardGridUtils";
import { api } from "@/lib/api";

export default function ExpandPanel({ item, seasonTab, setSeasonTab, selectedPaths, onToggleSelect, onToggleFolderSelect, onPlay, onSearch, onVideoDetail, onFolderDetail, onClose, batchMode, refreshKey = 0 }: {
  item: CardItem; seasonTab: number; setSeasonTab: (n: number) => void;
  selectedPaths: Set<string>; onToggleSelect: (p: string) => void; onToggleFolderSelect: (items: VideoInfo[]) => void;
  onPlay: (p: string) => void; onSearch: (q: string) => void; onVideoDetail: (v: VideoInfo) => void; onFolderDetail: (n: FolderNode) => void; onClose: () => void; batchMode?: boolean; refreshKey?: number;
}) {
  const [sortAsc, setSortAsc] = useState(true);
  // 完整度数据（tv 类型用）
  const tvPath = item.type === "tv" ? (item.parentNode?.path || "") : "";
  const [completeness, setCompleteness] = useState<any>(null);
  useEffect(() => {
    if (!tvPath) { setCompleteness(null); return; }
    api.getCompleteness(tvPath).then(res => { if (res.status === "ok") setCompleteness(res); }).catch(() => {});
  }, [tvPath]);
  const sortBtn = (
    <button onClick={() => setSortAsc(p => !p)}
      className="text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
      title={sortAsc ? "名称升序" : "名称降序"}>
      排序 {sortAsc ? "↑" : "↓"}
    </button>
  );
  if (item.type === "folder") {
    const folder = item.data;
    return (
      <>
        <div className="flex justify-between items-center mb-4">
          <span className="text-[15px] font-medium text-slate-200">{folder.name}</span>
          <div className="flex items-center gap-3">
            {sortBtn}
            {batchMode && <button onClick={() => onToggleFolderSelect(folder.videos)} className="text-xs text-blue-400 hover:text-blue-300">全选</button>}
            <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">✕</button>
          </div>
        </div>
        <EpisodeList videos={folder.videos} selectedPaths={selectedPaths} onToggleSelect={onToggleSelect} onPlay={onPlay} onSearch={onSearch} onVideoDetail={onVideoDetail} batchMode={batchMode} sortAsc={sortAsc} />
      </>
    );
  }
  if (item.type === "tv") {
    const activeSeason = seasonTab >= 0 ? item.seasons[seasonTab] : null;
    const allVideos = item.seasons.flatMap(s => s.videos || []);
    const isFlatTv = item.seasons.length === 1 && item.seasons[0] === item.parentNode;
    const isSingleSeason = item.seasons.length === 1;
    // 扁平 tv 或只有一季：直接展开集列表，不需要点季
    const directExpand = isFlatTv || isSingleSeason;
    const displayVideos = directExpand ? (item.seasons[0]?.videos || []) : (activeSeason?.videos || []);
    // 构建季号→完整度状态映射
    const seasonStatus: Record<number, { status: string; local: number; total: number }> = {};
    if (completeness?.seasons) {
      for (const s of completeness.seasons) {
        seasonStatus[s.season_number] = { status: s.status, local: s.local_count, total: s.episode_count };
      }
    }
    return (
      <>
        <div className="flex items-center justify-between mb-4">
          <span className="text-[15px] font-medium text-slate-200">{item.parentNode?.name || item.seriesName}</span>
          <div className="flex items-center gap-3">
            {sortBtn}
            {batchMode && <button onClick={() => onToggleFolderSelect(displayVideos.length ? displayVideos : allVideos)} className="text-xs text-blue-400 hover:text-blue-300">全选</button>}
            <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">✕</button>
          </div>
        </div>
        {/* 多季：季小卡片网格（扁平/单季时跳过） */}
        {!directExpand && (
          <div className="grid grid-cols-4 sm:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8 gap-3 mb-4">
            {item.seasons.map((s, idx) => {
              // 从季文件夹名提取季号
              const CN_NUM: Record<string, number> = { "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10 };
              const sMatch = s.name.match(/(?:Season|S)\s*(\d+)/i) || s.name.match(/第(\d+)季/);
              let sNum: number | undefined;
              if (sMatch) { sNum = parseInt(sMatch[1]); }
              else { const cnMatch = s.name.match(/第([一二三四五六七八九十]+)季/); if (cnMatch) { const c = cnMatch[1]; if (c.length === 1) sNum = CN_NUM[c]; else if (c === "十") sNum = 10; else if (c.startsWith("十")) sNum = 10 + (CN_NUM[c[1]] || 0); else if (c.endsWith("十")) sNum = (CN_NUM[c[0]] || 0) * 10; } }
              const sInfo = sNum != null ? seasonStatus[sNum] : undefined;
              return (
              <div key={s.path} className={`group rounded-xl overflow-hidden bg-[#1a1a1a] border cursor-pointer transition-all ${seasonTab === idx ? "border-blue-500/50 ring-1 ring-blue-500/20" : "border-white/[0.06] hover:border-slate-500"}`}
                onClick={() => { setSeasonTab(seasonTab === idx ? -1 : idx); onFolderDetail(s); }}>
                <div className="relative aspect-[2/3] bg-[#111]">
                  <CardPoster name={s.name} path={s.path} cacheKey={refreshKey} />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#1a1a1a] via-transparent to-transparent" />
                  <div className={`absolute top-2 left-2 text-white text-[10px] px-1.5 py-0.5 rounded-md font-bold ${sInfo?.status === "complete" ? "bg-emerald-600/80" : sInfo?.status === "partial" ? "bg-amber-600/80" : "bg-green-600/80"}`}>
                    {sInfo ? `${sInfo.local}/${sInfo.total}` : `${s.video_count} 集`}
                  </div>
                  {sInfo?.status === "complete" && <div className="absolute top-2 right-2 text-emerald-400 text-[10px]">✓</div>}
                  <div className="absolute bottom-0 left-0 right-0 p-2">
                    <p className="text-[12px] font-semibold text-white truncate">{getSeasonLabel(s.name)}</p>
                  </div>
                </div>
              </div>
              );
            })}
          </div>
        )}
        {/* 集列表：直接展开模式 或 选中了某个季 */}
        {(directExpand || activeSeason) && <EpisodeList videos={displayVideos} selectedPaths={selectedPaths} onToggleSelect={onToggleSelect} onPlay={onPlay} onSearch={onSearch} onVideoDetail={onVideoDetail} batchMode={batchMode} sortAsc={sortAsc} />}
      </>
    );
  }
  if (item.type === "series") {
    const folder = item.data;
    const children = folder.children || [];
    const allVideos = children.length > 0 ? children.flatMap(c => c.videos || []) : (folder.videos || []);
    const listItems = children.length > 0
      ? children.map(c => ({ name: c.name, path: c.path, video: c.videos?.[0] || null }))
      : (folder.videos || []).map(v => ({ name: v.file_name, path: v.file_path, video: v }));
    return (
      <>
        <div className="flex justify-between items-center mb-4">
          <span className="text-[15px] font-medium text-slate-200">{folder.name}</span>
          <div className="flex items-center gap-3">
            {batchMode && allVideos.length > 0 && <button onClick={() => onToggleFolderSelect(allVideos)} className="text-xs text-blue-400 hover:text-blue-300">全选</button>}
            <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">✕</button>
          </div>
        </div>
        <div className="space-y-1.5 overflow-y-auto no-scrollbar">
          {listItems.map((child) => (
            <div key={child.path} className="flex gap-3 px-3 py-2.5 rounded-lg hover:bg-white/[0.03] cursor-pointer transition-all"
              onClick={() => { if (child.video) onVideoDetail(child.video); }}>
              <div className="w-[50px] h-[70px] rounded-md overflow-hidden bg-[#222] flex-shrink-0 relative">
                <CardPoster name={child.name} path={child.path} cacheKey={refreshKey} />
              </div>
              <div className="flex-1 min-w-0 flex flex-col justify-center">
                <p className="text-[14px] text-slate-300 truncate">{child.name}</p>
                {child.video && (
                  <div className="flex items-center gap-2 mt-1">
                    {child.video.resolution && <span className="text-[11px] text-slate-600">{child.video.resolution}</span>}
                    {child.video.size_gb > 0 && <span className="text-[11px] text-slate-600">{child.video.size_gb.toFixed(1)}GB</span>}
                  </div>
                )}
              </div>
            </div>
          ))}
          {listItems.length === 0 && <p className="text-sm text-slate-600 py-6 text-center">暂无内容</p>}
        </div>
      </>
    );
  }
  if (item.type === "collection") {
    const folder = item.data;
    const children = folder.children || [];
    const allVideos = children.length > 0 ? children.flatMap(c => c.videos || []) : (folder.videos || []);
    const gridItems = children.length > 0
      ? children.map(c => ({ name: c.name, path: c.path, video: c.videos?.[0] || null }))
      : (folder.videos || []).map(v => ({ name: v.file_name, path: v.file_path, video: v }));
    return (
      <>
        <div className="flex justify-between items-center mb-4">
          <span className="text-[15px] font-medium text-slate-200">{folder.name}</span>
          <div className="flex items-center gap-3">
            {batchMode && allVideos.length > 0 && <button onClick={() => onToggleFolderSelect(allVideos)} className="text-xs text-blue-400 hover:text-blue-300">全选</button>}
            <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">✕</button>
          </div>
        </div>
        <div className="grid grid-cols-4 sm:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8 gap-3 overflow-y-auto no-scrollbar">
          {gridItems.map((child) => (
            <div key={child.path} className="group rounded-xl overflow-hidden bg-[#1a1a1a] border border-white/[0.06] hover:border-slate-500 cursor-pointer transition-all"
              onClick={() => { if (child.video) onVideoDetail(child.video); }}>
              <div className="relative aspect-[2/3] bg-[#111]">
                <CardPoster name={child.name} path={child.path} cacheKey={refreshKey} />
                <div className="absolute inset-0 bg-gradient-to-t from-[#1a1a1a] via-transparent to-transparent" />
                {child.video && (
                  <div className="absolute top-2 right-2 flex flex-col gap-1 z-10">
                    {child.video.is_low_res && <span className="bg-orange-500/90 text-white text-[10px] px-1.5 py-0.5 rounded-md font-medium">低画质</span>}
                  </div>
                )}
                <div className="absolute bottom-0 left-0 right-0 p-3">
                  <p className="text-[13px] font-semibold text-white truncate">{child.name}</p>
                  {child.video && <p className="text-[11px] text-slate-400 mt-0.5">{child.video.resolution}{child.video.size_gb > 0 ? ` · ${child.video.size_gb.toFixed(1)}GB` : ""}</p>}
                </div>
              </div>
            </div>
          ))}
          {gridItems.length === 0 && <p className="col-span-full text-sm text-slate-600 py-6 text-center">暂无内容</p>}
        </div>
      </>
    );
  }
  return null;
}
