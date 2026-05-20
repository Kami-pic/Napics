// 卡片网格
"use client";
import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";
import type { VideoInfo, FolderNode } from "@/types";
import { formatSize, isLeafFolder } from "@/lib/utils";
import { getCategoryTagLabel } from "@/lib/folderTypes";
import ExpandPanel from "./ExpandPanel";
import CardPoster from "./CardPoster";

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
  onAddLibrary?: () => void;
}

export function getSeasonLabel(name: string): string {
  const m = name.match(/(?:S(\d+)|第(\d+)季|Season\s*(\d+))/i);
  if (m) return `第${parseInt(m[1] || m[2] || m[3])}季`;
  return name;
}
function getSeasonNum(name: string): number {
  // 阿拉伯数字格式：S01、第3季、Season 2
  const m = name.match(/(?:S(\d+)|第(\d+)季|Season\s*(\d+))/i);
  if (m) return parseInt(m[1] || m[2] || m[3]);
  // 中文数字格式：第一季、第二季...
  const cnMap: Record<string, number> = { "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15, "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20 };
  const cnMatch = name.match(/第([一二三四五六七八九十]+)季/);
  if (cnMatch) return cnMap[cnMatch[1]] || 0;
  return 0;
}
function compareSeasons(a: FolderNode, b: FolderNode): number {
  const numA = getSeasonNum(a.name);
  const numB = getSeasonNum(b.name);
  if (numA !== numB) return numA - numB;
  // 都无法提取季号时按名字自然排序
  return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });
}
function getSeriesPrefix(name: string): string | null {
  const m = name.match(/^(.+?)[\s._-]*(?:S\d+|第\d+季|Season\s*\d+)$/i);
  return m ? m[1].trim() : null;
}

export type CardItem =
  | { type: "folder"; data: FolderNode; id: string }
  | { type: "video"; data: VideoInfo; id: string }
  | { type: "tv"; seriesName: string; seasons: FolderNode[]; id: string; parentNode?: FolderNode }
  | { type: "series"; data: FolderNode; id: string }
  | { type: "collection"; data: FolderNode; id: string };

export default function CardGrid({
  currentFolder, groupedVideos, selectedPaths, batchMode, refreshKey = 0,
  onToggleSelect, onToggleFolderSelect, onPlay, onSearch, onNavigate,
  onVideoDetail, onFolderDetail, onAddLibrary,
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

  // 只在 currentFolder 的 path 真正变化时才折叠展开面板（刷新不折叠）
  const prevFolderPath = useRef(currentFolder?.path ?? "");
  useEffect(() => {
    const curPath = currentFolder?.path ?? "";
    if (curPath !== prevFolderPath.current) {
      setExpandedId(null); setExpandPos(null);
      prevFolderPath.current = curPath;
    }
  }, [currentFolder]);

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

    // 虚拟媒体库文件夹内部：把自身当作一个内容项渲染
    // 进入紫色文件夹后，看到的是一个完整的内容卡片（tv/movie/collection），而不是散落的子目录或视频
    if (currentFolder.is_virtual_library) {
      const ft = currentFolder.folder_type || "";
      if (ft === "tv" && children.length > 0) {
        // tv 类型：显示为 tv 卡片，children 作为季目录
        const seasons = [...children].sort(compareSeasons);
        results.push({ type: "tv", seriesName: currentFolder.name, seasons, id: `ms-${currentFolder.path}`, parentNode: currentFolder });
      } else if (ft === "tv" && children.length === 0 && currentFolder.videos?.length > 0) {
        // 扁平 tv（无季目录，直接有视频）
        results.push({ type: "tv", seriesName: currentFolder.name, seasons: [currentFolder], id: `ms-${currentFolder.path}`, parentNode: currentFolder });
      } else if (ft === "movie" && currentFolder.videos?.length === 1) {
        // 单个电影
        const v = currentFolder.videos[0];
        results.push({ type: "video", data: v, id: `v-${v.file_path}-0` });
      } else if ((ft === "collection" || ft === "series") && children.length > 0) {
        // collection/series
        results.push({ type: ft === "series" ? "series" : "collection", data: currentFolder, id: `${ft}-${currentFolder.path}` });
      } else {
        // 其他情况：正常渲染 children 和 videos
        children.forEach(node => results.push({ type: "folder", data: node, id: `f-${node.path}` }));
        Object.entries(groupedVideos).forEach(([, vids]) => {
          vids.forEach((v, vi) => results.push({ type: "video", data: v, id: `v-${v.file_path}-${vi}` }));
        });
      }
      return results;
    }

    const seriesGroups: Record<string, FolderNode[]> = {};
    const standalone: FolderNode[] = [];
    children.forEach(node => {
      const ft = node.folder_type || "";
      // 虚拟媒体库文件夹始终作为独立文件夹卡片显示，不按 folder_type 展开
      if (node.is_virtual_library) {
        standalone.push(node);
        return;
      }
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
          const seasons = [...node.children].sort(compareSeasons);
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
        nodes.sort(compareSeasons);
        results.push({ type: "tv", seriesName: name, seasons: nodes, id: `ms-${name}` });
      } else { standalone.push(nodes[0]); }
    });
    // 媒体文件夹置顶，插入到 results 最前面
    const pinned = standalone.filter(n => n.is_virtual_library);
    const normal = standalone.filter(n => !n.is_virtual_library);
    const pinnedItems: CardItem[] = pinned.map(node => ({ type: "folder", data: node, id: `f-${node.path}` }));
    normal.forEach(node => results.push({ type: "folder", data: node, id: `f-${node.path}` }));
    // 将 pinned 插入到 results 最前面
    results.unshift(...pinnedItems);
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

  // 只在根目录（currentFolder 是树的根节点）时显示添加卡片
  const isRootLevel = currentFolder?.path === "" || !currentFolder?.path;

  return (
    <div className="animate-in fade-in duration-200">
      <div ref={gridRef} className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-5 pb-20">
        {/* 常驻添加卡片：仅根目录第一张 */}
        {isRootLevel && onAddLibrary && (
          <div data-card>
            <button onClick={onAddLibrary}
              className="group w-full aspect-[2/3] rounded-xl border-2 border-dashed border-white/[0.08] hover:border-blue-500/30 bg-white/[0.02] hover:bg-blue-500/[0.03] flex flex-col items-center justify-center gap-3 transition-all cursor-pointer">
              <div className="w-10 h-10 rounded-full bg-white/[0.04] group-hover:bg-blue-500/10 flex items-center justify-center transition-all">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-500 group-hover:text-blue-400 transition-colors">
                  <path d="M12 5v14M5 12h14" />
                </svg>
              </div>
              <span className="text-xs text-slate-500 group-hover:text-slate-300 transition-colors">添加媒体文件夹</span>
            </button>
          </div>
        )}
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
              // 虚拟媒体库文件夹：始终作为文件夹进入，不当作单个电影处理
              if (folder.is_virtual_library) {
                onFolderDetail(folder);
                setExpandedId(null); setExpandPos(null);
                onNavigate(folder);
              } else if (ft === "movie" && folder.videos[0]) {
                // movie 类型：显示视频详情（不是文件夹详情）
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
                className={`group rounded-xl overflow-hidden bg-[#1a1a1a] border cursor-pointer transition-all ${isActive ? "border-blue-500/50 ring-1 ring-blue-500/20" : folder.is_virtual_library ? "border-2 border-blue-500/30 hover:border-blue-500/50" : "border-white/[0.06] hover:border-slate-500"}`}
                onClick={handleClick}>
                {hasPoster ? (
                  <div className="relative aspect-[2/3] bg-[#111]">
                    <CardPoster name={folder.name} path={folder.path} cacheKey={refreshKey} cover={folder.is_virtual_library || (ft === "collection" || ft === "series" || ft === "mixed" || (ft !== "movie" && ft !== "tv" && ft !== "season" && folder.children?.length > 0))} />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#1a1a1a] via-transparent to-transparent" />
                    {leaf && ft !== "movie" && !folder.is_virtual_library && (
                      <div className="absolute top-3 left-3 bg-green-600 text-white text-[12px] px-2.5 py-1 rounded-lg font-bold">{folder.video_count} 集</div>
                    )}
                    {folder.is_virtual_library && (
                      <div className="absolute top-3 left-3 text-white text-[11px] px-2 py-0.5 rounded-md font-medium tracking-wide bg-blue-500/30 text-blue-300">
                        {getCategoryTagLabel(folder.category_tag || "")}
                      </div>
                    )}
                    {!folder.is_virtual_library && folder.category_tag && (
                      <div className={`absolute top-3 left-3 text-white text-[11px] px-2 py-0.5 rounded-md font-medium tracking-wide ${folder.category_tag === "movie" ? "bg-blue-500/30 text-blue-300" : "bg-green-500/30 text-green-300"}`}>
                        {getCategoryTagLabel(folder.category_tag)}
                      </div>
                    )}
                    {ft === "movie" && !folder.is_virtual_library && folder.videos[0] && (
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
                        {folder.is_virtual_library
                          ? `${folder.video_count} 个项目`
                          : ft === "movie" && folder.videos[0]
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


