// 卡片网格
"use client";
import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";
import type { VideoInfo, FolderNode } from "@/types";
import { api } from "@/lib/api";
import { formatSize, isLeafFolder } from "@/lib/utils";
import { getCategoryTagLabel, getFolderTypeLabel } from "@/lib/folderTypes";

interface CardGridProps {
  currentFolder: FolderNode | null;
  groupedVideos: Record<string, VideoInfo[]>;
  selectedPaths: Set<string>;
  batchMode: boolean;
  refreshKey?: number;
  onToggleSelect: (path: string) => void;
  onToggleFolderSelect: (items: VideoInfo[]) => void;
  onPlay: (path: string) => void;
  onSearch: (query: string) => void;
  onNavigate: (node: FolderNode) => void;
  onVideoDetail: (v: VideoInfo) => void;
  onFolderDetail: (n: FolderNode) => void;
}

function getSeasonLabel(name: string): string {
  const m = name.match(/(?:S(\d+)|第(\d+)季|Season\s*(\d+))/i);
  if (m) return `第${parseInt(m[1] || m[2] || m[3])}季`;
  return name;
}
function getSeasonNum(name: string): number {
  const m = name.match(/(?:S(\d+)|第(\d+)季|Season\s*(\d+))/i);
  return m ? parseInt(m[1] || m[2] || m[3]) : 0;
}
function getSeriesPrefix(name: string): string | null {
  const m = name.match(/^(.+?)[\s._-]*(?:S\d+|第\d+季|Season\s*\d+)$/i);
  return m ? m[1].trim() : null;
}

type CardItem =
  | { type: "folder"; data: FolderNode; id: string }
  | { type: "video"; data: VideoInfo; id: string }
  | { type: "tv"; seriesName: string; seasons: FolderNode[]; id: string; parentNode?: FolderNode }
  | { type: "series"; data: FolderNode; id: string }
  | { type: "collection"; data: FolderNode; id: string };

export default function CardGrid({
  currentFolder, groupedVideos, selectedPaths, batchMode, refreshKey = 0,
  onToggleSelect, onToggleFolderSelect, onPlay, onSearch, onNavigate,
  onVideoDetail, onFolderDetail,
}: CardGridProps) {
  const [limit, setLimit] = useState(48);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [seasonTab, setSeasonTab] = useState(-1);  // -1 = 未选中任何季
  const gridRef = useRef<HTMLDivElement>(null);
  const [expandPos, setExpandPos] = useState<{ afterIndex: number } | null>(null);

  const handleExpand = useCallback((id: string, index: number) => {
    if (expandedId === id) { 
      setExpandedId(null); setExpandPos(null); 
    }
    else { setExpandedId(id); setSeasonTab(-1); setExpandPos({ afterIndex: index }); }
  }, [expandedId]);

  useEffect(() => { setExpandedId(null); setExpandPos(null); }, [currentFolder]);

  // 全局点击：点击展开面板、卡片、详情面板、按钮以外的区域 → 折叠展开面板
  useEffect(() => {
    if (!expandedId) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest('[data-card]') || target.closest('[data-expand-panel]') || 
          target.closest('[data-detail-drawer]') || target.closest('button') || 
          target.closest('input') || target.closest('textarea')) {
        return;
      }
      setExpandedId(null); setExpandPos(null);
      // 不在这里切换详情面板 — 让各卡片的 onClick 自己决定
    };
    const timer = setTimeout(() => document.addEventListener('click', handler), 100);
    return () => { clearTimeout(timer); document.removeEventListener('click', handler); };
  }, [expandedId, currentFolder, onFolderDetail]);

  const items = useMemo((): CardItem[] => {
    if (!currentFolder) return [];
    const results: CardItem[] = [];
    const children = currentFolder.children || [];
    const seriesGroups: Record<string, FolderNode[]> = {};
    const standalone: FolderNode[] = [];
    children.forEach(node => {
      const ft = node.folder_type || "";
      // 用 folder_type 优先判断
      if (ft === "series") {
        results.push({ type: "series", data: node, id: `sc-${node.path}` });
        return;
      }
      if (ft === "collection") {
        results.push({ type: "collection", data: node, id: `mc-${node.path}` });
        return;
      }
      // tv 类型 → 展开（有子目录显示季卡片，无子目录直接显示集列表）
      if (ft === "tv") {
        if (node.children.length > 0) {
          const seasons = [...node.children].sort((a, b) => getSeasonNum(a.name) - getSeasonNum(b.name));
          results.push({ type: "tv", seriesName: node.name, seasons, id: `ms-${node.path}`, parentNode: node });
        } else {
          // 扁平 tv（无季目录，直接有视频）→ 当作只有一个虚拟季的 tv
          results.push({ type: "tv", seriesName: node.name, seasons: [node], id: `ms-${node.path}`, parentNode: node });
        }
        return;
      }
      // 兼容旧逻辑：没有 folder_type 时用文件名前缀匹配
      const prefix = getSeriesPrefix(node.name);
      if (prefix) {
        if (!seriesGroups[prefix]) seriesGroups[prefix] = [];
        seriesGroups[prefix].push(node);
      } else { standalone.push(node); }
    });
    Object.entries(seriesGroups).forEach(([name, nodes]) => {
      if (nodes.length > 1) {
        nodes.sort((a, b) => getSeasonNum(a.name) - getSeasonNum(b.name));
        results.push({ type: "tv", seriesName: name, seasons: nodes, id: `ms-${name}` });
      } else { standalone.push(nodes[0]); }
    });
    standalone.forEach(node => results.push({ type: "folder", data: node, id: `f-${node.path}` }));
    Object.entries(groupedVideos).forEach(([, vids]) => {
      vids.forEach((v, vi) => results.push({ type: "video", data: v, id: `v-${v.file_path}-${vi}` }));
    });
    return results;
  }, [currentFolder, groupedVideos]);

  const getRowEndIndex = useCallback((clickIndex: number): number => {
    if (!gridRef.current) return clickIndex;
    const cards = gridRef.current.querySelectorAll<HTMLElement>('[data-card]');
    if (!cards[clickIndex]) return clickIndex;
    const clickTop = cards[clickIndex].offsetTop;
    let lastInRow = clickIndex;
    for (let i = clickIndex + 1; i < cards.length; i++) {
      if (cards[i].offsetTop === clickTop) lastInRow = i; else break;
    }
    return lastInRow;
  }, []);

  const rowEndIndex = expandPos ? getRowEndIndex(expandPos.afterIndex) : -1;
  const expandedItem = expandedId ? items.find(it => it.id === expandedId) : null;
  if (!currentFolder) return null;
  const visibleItems = items.slice(0, limit);

  const renderList: (CardItem | { type: "expand" })[] = [];
  visibleItems.forEach((item, i) => {
    renderList.push(item);
    if (i === rowEndIndex && expandedItem) renderList.push({ type: "expand" });
  });
  if (expandedItem && rowEndIndex >= visibleItems.length) renderList.push({ type: "expand" });

  // 封面逻辑：所有文件夹都尝试显示封面
  const showFolderPoster = (_folder: FolderNode) => true;

  return (
    <div className="animate-in fade-in duration-200">
      <div ref={gridRef} className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-5 pb-20">
        {renderList.map((entry, ri) => {
          if ("type" in entry && entry.type === "expand" && expandedItem) {
            return (
              <div key="expand-panel" data-expand-panel className="col-span-full bg-[#141414] border border-white/[0.06] rounded-xl p-5 animate-in fade-in duration-200">
                <ExpandPanel item={expandedItem} seasonTab={seasonTab} setSeasonTab={setSeasonTab}
                  selectedPaths={selectedPaths} onToggleSelect={onToggleSelect} onToggleFolderSelect={onToggleFolderSelect}
                  onPlay={onPlay} onSearch={onSearch} onVideoDetail={onVideoDetail} onFolderDetail={onFolderDetail}
                  onClose={() => { setExpandedId(null); setExpandPos(null); }} batchMode={batchMode} refreshKey={refreshKey} />
              </div>
            );
          }
          const item = entry as CardItem;
          const itemIndex = visibleItems.indexOf(item);
          const isActive = expandedId === item.id;

          if (item.type === "folder") {
            const folder = item.data;
            const leaf = isLeafFolder(folder) && !folder.is_category;
            const hasPoster = showFolderPoster(folder);
            const ft = folder.folder_type || "";
            // 末端文件夹 → 展开；非末端 → 进入
            const handleClick = () => {
              // movie 类型：显示视频详情（不是文件夹详情）
              if (ft === "movie" && folder.videos[0]) {
                onVideoDetail(folder.videos[0]);
                setExpandedId(null); setExpandPos(null);
              } else {
                onFolderDetail(folder);
                if (leaf) handleExpand(item.id, itemIndex);
                else { setExpandedId(null); setExpandPos(null); onNavigate(folder); }
              }
            };

            return (
              <div key={item.id} data-card
                className={`group rounded-xl overflow-hidden bg-[#1a1a1a] border cursor-pointer transition-all ${isActive ? "border-blue-500/50 ring-1 ring-blue-500/20" : "border-white/[0.06] hover:border-slate-500"}`}
                onClick={handleClick}>
                {hasPoster ? (
                  <div className="relative aspect-[2/3] bg-[#111]">
                    <CardPoster name={folder.name} path={folder.path} cacheKey={refreshKey} cover={ft === "collection" || ft === "series" || ft === "mixed" || (ft !== "movie" && ft !== "tv" && ft !== "season" && folder.children?.length > 0)} />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#1a1a1a] via-transparent to-transparent" />
                    {leaf && ft !== "movie" && (
                      <div className="absolute top-3 left-3 bg-green-600 text-white text-[12px] px-2.5 py-1 rounded-lg font-bold">{folder.video_count} 集</div>
                    )}
                    {folder.category_tag && (
                      <div className={`absolute top-3 left-3 text-white text-[11px] px-2 py-0.5 rounded-md font-medium tracking-wide ${folder.category_tag === "movie" ? "bg-blue-500/30 text-blue-300" : "bg-green-500/30 text-green-300"}`}>
                        {getCategoryTagLabel(folder.category_tag)}
                      </div>
                    )}
                    {ft === "movie" && folder.videos[0] && (
                      <div className="absolute top-3 right-3 flex flex-col gap-1 z-10">
                        {folder.videos[0].is_low_res && <span className="bg-orange-500/90 text-white text-[11px] px-2 py-0.5 rounded-md font-medium">低画质</span>}
                        {folder.videos[0].hdr_type && folder.videos[0].hdr_type !== "SDR" && <span className="bg-purple-500/90 text-white text-[11px] px-2 py-0.5 rounded-md font-medium">{folder.videos[0].hdr_type}</span>}
                      </div>
                    )}
                    {batchMode && (
                      <div className="absolute top-3 right-3 z-10">
                        <input type="checkbox" onChange={() => onToggleFolderSelect(folder.videos)} onClick={e => e.stopPropagation()}
                          className="w-5 h-5 rounded bg-black/50 border-white/20 cursor-pointer" />
                      </div>
                    )}
                    <div className="absolute bottom-0 left-0 right-0 p-4">
                      <p className="text-[15px] font-semibold text-white truncate">{folder.name}</p>
                      <p className="text-xs text-slate-400 mt-1">
                        {ft === "movie" && folder.videos[0]
                          ? `${folder.videos[0].resolution || ""} · ${formatSize(folder.videos[0].size_gb)}`
                          : leaf ? "点击展开" : `${folder.video_count} 个项目`}
                      </p>
                    </div>
                  </div>
                ) : (
                  /* 无封面模式：纯文字卡片 */
                  <div className="aspect-[2/3] bg-[#111] flex flex-col justify-end p-4 relative">
                    <div className="absolute inset-0 flex items-center justify-center opacity-[0.04] text-[80px] select-none">📂</div>
                    {batchMode && (
                      <div className="absolute top-3 right-3 z-10">
                        <input type="checkbox" onChange={() => onToggleFolderSelect(folder.videos)} onClick={e => e.stopPropagation()}
                          className="w-5 h-5 rounded bg-black/50 border-white/20 cursor-pointer" />
                      </div>
                    )}
                    <p className="text-[15px] font-semibold text-white truncate relative z-10">{folder.name}</p>
                    <p className="text-xs text-slate-500 mt-1 relative z-10">{folder.video_count} 个项目</p>
                  </div>
                )}
              </div>
            );
          }

          if (item.type === "tv") {
            const totalEps = item.seasons.reduce((s, n) => s + n.video_count, 0);
            return (
              <div key={item.id} data-card
                className={`group rounded-xl overflow-hidden bg-[#1a1a1a] border cursor-pointer transition-all ${isActive ? "border-blue-500/50 ring-1 ring-blue-500/20" : "border-white/[0.06] hover:border-slate-500"}`}
                onClick={() => { onFolderDetail(item.parentNode || item.seasons[0]); handleExpand(item.id, itemIndex); }}>
                <div className="relative aspect-[2/3] bg-[#111]">
                  <CardPoster name={item.seriesName} path={item.parentNode?.path || item.seasons[0]?.path} cacheKey={refreshKey} />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#1a1a1a] via-transparent to-transparent" />
                  <div className="absolute top-3 left-3 bg-green-600 text-white text-[12px] px-2.5 py-1 rounded-lg font-bold">{item.seasons.length} 季 · {totalEps} 集</div>
                  <div className="absolute bottom-0 left-0 right-0 p-4">
                    <p className="text-[15px] font-semibold text-white truncate">{item.parentNode?.name || item.seriesName}</p>
                    <p className="text-xs text-slate-400 mt-1">{isActive ? "收起" : "展开"}</p>
                  </div>
                </div>
              </div>
            );
          }

          if (item.type === "series") {
            const folder = item.data;
            const childCount = folder.children.length || folder.video_count;
            return (
              <div key={item.id} data-card
                className={`group rounded-xl overflow-hidden bg-[#1a1a1a] border cursor-pointer transition-all ${isActive ? "border-blue-500/50 ring-1 ring-blue-500/20" : "border-white/[0.06] hover:border-slate-500"}`}
                onClick={() => { onFolderDetail(folder); handleExpand(item.id, itemIndex); }}>
                <div className="relative aspect-[2/3] bg-[#111]">
                  <CardPoster name={folder.name} path={folder.path} cacheKey={refreshKey} cover />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#1a1a1a] via-transparent to-transparent" />
                  <div className="absolute top-3 left-3 bg-blue-600 text-white text-[12px] px-2.5 py-1 rounded-lg font-bold">{childCount} 部</div>
                  <div className="absolute bottom-0 left-0 right-0 p-4">
                    <p className="text-[15px] font-semibold text-white truncate">{folder.name}</p>
                    <p className="text-xs text-slate-400 mt-1">{isActive ? "收起" : "系列"}</p>
                  </div>
                </div>
              </div>
            );
          }

          if (item.type === "collection") {
            const folder = item.data;
            const childCount = folder.children.length || folder.video_count;
            return (
              <div key={item.id} data-card
                className={`group rounded-xl overflow-hidden bg-[#1a1a1a] border cursor-pointer transition-all ${isActive ? "border-blue-500/50 ring-1 ring-blue-500/20" : "border-white/[0.06] hover:border-slate-500"}`}
                onClick={() => { onFolderDetail(folder); handleExpand(item.id, itemIndex); }}>
                <div className="relative aspect-[2/3] bg-[#111]">
                  <CardPoster name={folder.name} path={folder.path} cacheKey={refreshKey} cover />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#1a1a1a] via-transparent to-transparent" />
                  <div className="absolute top-3 left-3 bg-slate-600 text-white text-[12px] px-2.5 py-1 rounded-lg font-bold">{childCount} 部</div>
                  <div className="absolute bottom-0 left-0 right-0 p-4">
                    <p className="text-[15px] font-semibold text-white truncate">{folder.name}</p>
                    <p className="text-xs text-slate-400 mt-1">{isActive ? "收起" : "合集"}</p>
                  </div>
                </div>
              </div>
            );
          }

          if (item.type === "video") {
            const v = item.data;
            const sel = selectedPaths.has(v.file_path);
            return (
              <div key={item.id} data-card className={`group rounded-xl overflow-hidden bg-[#1a1a1a] border cursor-pointer transition-all ${sel ? "border-blue-500/40 ring-1 ring-blue-500/20" : "border-white/[0.06] hover:border-slate-500"}`}
                onClick={() => { setExpandedId(null); setExpandPos(null); onVideoDetail(v); }}>
                <div className="relative aspect-[2/3] bg-[#111]">
                  <CardPoster name={v.file_name} path={v.file_path} cacheKey={refreshKey} />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#1a1a1a] via-transparent to-transparent" />
                  {batchMode && (
                    <div className={`absolute top-3 left-3 z-10 ${sel ? 'opacity-100' : 'opacity-70'}`}>
                      <input type="checkbox" checked={sel} onChange={() => onToggleSelect(v.file_path)} onClick={e => e.stopPropagation()}
                        className="w-5 h-5 rounded bg-black/50 border-white/20 checked:bg-blue-500 cursor-pointer" />
                    </div>
                  )}
                  <div className="absolute top-3 right-3 flex flex-col gap-1 z-10">
                    {v.is_low_res && <span className="bg-orange-500/90 text-white text-[11px] px-2 py-0.5 rounded-md font-medium">低画质</span>}
                    {v.hdr_type !== "SDR" && <span className="bg-purple-500/90 text-white text-[11px] px-2 py-0.5 rounded-md font-medium">{v.hdr_type}</span>}
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 p-4">
                    <p className="text-[15px] font-semibold text-white truncate flex items-center gap-1.5">
                      {!v.shadow_name && !v.organize_status && <span title="未整理" className="inline-block w-2 h-2 rounded-full bg-slate-500 flex-shrink-0" />}
                      {v.organize_status === "scrape_failed" && <span title="刮削失败" className="text-orange-400 flex-shrink-0">⚠</span>}
                      {v.file_name}
                    </p>
                    <p className="text-xs text-slate-400 mt-1">{v.resolution} · {formatSize(v.size_gb)}</p>
                  </div>
                </div>
              </div>
            );
          }
          return null;
        })}
      </div>
      {items.length > limit && (
        <div className="flex justify-center py-10">
          <button onClick={() => setLimit(p => p + 48)} className="px-8 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-sm text-slate-400 hover:text-white hover:bg-white/[0.08] transition-all">加载更多</button>
        </div>
      )}
    </div>
  );
}

/** 展开面板 */
function ExpandPanel({ item, seasonTab, setSeasonTab, selectedPaths, onToggleSelect, onToggleFolderSelect, onPlay, onSearch, onVideoDetail, onFolderDetail, onClose, batchMode, refreshKey = 0 }: {
  item: CardItem; seasonTab: number; setSeasonTab: (n: number) => void;
  selectedPaths: Set<string>; onToggleSelect: (p: string) => void; onToggleFolderSelect: (items: VideoInfo[]) => void;
  onPlay: (p: string) => void; onSearch: (q: string) => void; onVideoDetail: (v: VideoInfo) => void; onFolderDetail: (n: FolderNode) => void; onClose: () => void; batchMode?: boolean; refreshKey?: number;
}) {
  if (item.type === "folder") {
    const folder = item.data;
    return (
      <>
        <div className="flex justify-between items-center mb-4">
          <span className="text-[15px] font-medium text-slate-200">{folder.name}</span>
          <div className="flex items-center gap-3">
            {batchMode && <button onClick={() => onToggleFolderSelect(folder.videos)} className="text-xs text-blue-400 hover:text-blue-300">全选</button>}
            <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">✕</button>
          </div>
        </div>
        <EpisodeList videos={folder.videos} selectedPaths={selectedPaths} onToggleSelect={onToggleSelect} onPlay={onPlay} onSearch={onSearch} onVideoDetail={onVideoDetail} batchMode={batchMode} />
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
    return (
      <>
        <div className="flex items-center justify-between mb-4">
          <span className="text-[15px] font-medium text-slate-200">{item.parentNode?.name || item.seriesName}</span>
          <div className="flex items-center gap-3">
            {batchMode && <button onClick={() => onToggleFolderSelect(displayVideos.length ? displayVideos : allVideos)} className="text-xs text-blue-400 hover:text-blue-300">全选</button>}
            <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">✕</button>
          </div>
        </div>
        {/* 多季：季小卡片网格（扁平/单季时跳过） */}
        {!directExpand && (
          <div className="grid grid-cols-4 sm:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8 gap-3 mb-4">
            {item.seasons.map((s, idx) => (
              <div key={s.path} className={`group rounded-xl overflow-hidden bg-[#1a1a1a] border cursor-pointer transition-all ${seasonTab === idx ? "border-blue-500/50 ring-1 ring-blue-500/20" : "border-white/[0.06] hover:border-slate-500"}`}
                onClick={() => { setSeasonTab(seasonTab === idx ? -1 : idx); onFolderDetail(s); }}>
                <div className="relative aspect-[2/3] bg-[#111]">
                  <CardPoster name={s.name} path={s.path} cacheKey={refreshKey} />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#1a1a1a] via-transparent to-transparent" />
                  <div className="absolute top-2 left-2 bg-green-600/80 text-white text-[10px] px-1.5 py-0.5 rounded-md font-bold">{s.video_count} 集</div>
                  <div className="absolute bottom-0 left-0 right-0 p-2">
                    <p className="text-[12px] font-semibold text-white truncate">{getSeasonLabel(s.name)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        {/* 集列表：直接展开模式 或 选中了某个季 */}
        {(directExpand || activeSeason) && <EpisodeList videos={displayVideos} selectedPaths={selectedPaths} onToggleSelect={onToggleSelect} onPlay={onPlay} onSearch={onSearch} onVideoDetail={onVideoDetail} batchMode={batchMode} />}
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
        <div className="space-y-1.5 max-h-[400px] overflow-y-auto no-scrollbar">
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
        <div className="grid grid-cols-4 sm:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8 gap-3 max-h-[400px] overflow-y-auto no-scrollbar">
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

function EpisodeList({ videos, selectedPaths, onToggleSelect, onPlay, onSearch, onVideoDetail, batchMode }: {
  videos: VideoInfo[]; selectedPaths: Set<string>; onToggleSelect: (p: string) => void;
  onPlay: (p: string) => void; onSearch: (q: string) => void; onVideoDetail: (v: VideoInfo) => void; batchMode?: boolean;
}) {
  return (
    <div className="space-y-1 max-h-[400px] overflow-y-auto no-scrollbar">
      {videos.map((v, idx) => (
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
            {v.organize_status === "scrape_failed" && <span title="刮削失败" className="text-orange-400 text-xs flex-shrink-0">⚠</span>}
            {v.file_name}
          </p>
          <span className="text-xs text-slate-600 flex-shrink-0">{v.resolution}</span>
          <span className="text-xs text-slate-600 flex-shrink-0">{formatSize(v.size_gb)}</span>
          <button onClick={(e) => { e.stopPropagation(); onPlay(v.file_path); }} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all flex-shrink-0">
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
          </button>
          <button onClick={(e) => { e.stopPropagation(); onSearch(v.file_name); }} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-blue-400 hover:bg-blue-500/10 transition-all flex-shrink-0">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" /></svg>
          </button>
        </div>
      ))}
      {videos.length === 0 && <p className="text-sm text-slate-600 py-6 text-center">暂无视频文件</p>}
    </div>
  );
}

/** 封面 — 优先本地海报，fallback 到 scrape data 的远程 poster_url */
function CardPoster({ name, path, cacheKey = 0, cover = false }: { name: string; path?: string; cacheKey?: number; cover?: boolean }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const [remoteSrc, setRemoteSrc] = useState<string | null>(null);
  const [stage, setStage] = useState<"local" | "remote" | "done">("local");
  const everLoadedRef = useRef(false); // 曾经加载成功过就不再显示 spinner
  const bust = cacheKey ? `&_t=${cacheKey}` : "";
  const coverParam = cover ? "&cover=true" : "";
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const localSrc = path ? `${API_BASE}/scrape/poster?path=${encodeURIComponent(path)}${coverParam}${bust}` : null;

  // cacheKey 变化时重置状态（刮削/删除后刷新）
  useEffect(() => {
    setLoaded(false); setError(false); setRemoteSrc(null); setStage("local");
  }, [cacheKey, path]);

  const src = stage === "local" ? localSrc : stage === "remote" ? remoteSrc : null;

  return (
    <>
      {!loaded && !everLoadedRef.current && !error && stage !== "done" && src && <div className="absolute inset-0 flex items-center justify-center bg-[#111]"><div className="w-6 h-6 border-2 border-slate-800 border-t-slate-500 rounded-full animate-spin" /></div>}
      {(error || stage === "done" || !src) && <div className="absolute inset-0 bg-[#111] flex items-center justify-center"><span className="text-slate-700 text-3xl">🎬</span></div>}
      {src && stage !== "done" && <img src={src} alt="" loading="eager" decoding="sync"
        className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${(loaded || everLoadedRef.current) ? "opacity-100" : "opacity-0"}`}
        onLoad={() => { setLoaded(true); everLoadedRef.current = true; }}
        onError={() => {
          if (stage === "local" && path && !cover) {
            // 本地没有，尝试读 NFO 拿远程 URL（仅刮削单元，聚合容器不读 NFO）
            setStage("done");
            api.readScrape(path, true).then(r => {
              if (r.status === "ok" && r.data?.poster_url) {
                const proxyUrl = `${API_BASE}/proxy/image?url=${encodeURIComponent(r.data.poster_url)}`;
                setRemoteSrc(proxyUrl);
                setStage("remote");
                setLoaded(false);
                setError(false);
              }
            }).catch(() => {});
          } else {
            setStage("done");
          }
        }} />}
    </>
  );
}
