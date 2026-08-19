// 当前目录表格视图 — 含子目录和视频
"use client";
import React, { useMemo, useState } from "react";
import type { VideoInfo, FolderNode } from "@/types";
import { formatSize } from "@/lib/utils";

interface FolderTableProps {
  currentFolder: FolderNode | null;
  selectedPaths: Set<string>;
  onToggleSelect: (path: string) => void;
  onPlay: (path: string) => void;
  onSearch: (query: string, ctx?: { cnName?: string; enName?: string; originalName?: string; folderType?: string; savePath?: string }) => void;
  onNavigate: (node: FolderNode) => void;
  onVideoDetail: (v: VideoInfo) => void;
  onFolderDetail: (n: FolderNode) => void;
  batchMode?: boolean;
}

type SortKey = "name" | "resolution" | "size" | "type";

export default function FolderTable({
  currentFolder, selectedPaths, onToggleSelect, onPlay, onSearch, onNavigate, onVideoDetail, onFolderDetail, batchMode,
}: FolderTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortAsc, setSortAsc] = useState(true);
  const [page, setPage] = useState(0);
  const pageSize = 50;

  const rows = useMemo(() => {
    if (!currentFolder) return [];
    const items: { type: "folder" | "video"; name: string; resolution: string; size: number; data: any }[] = [];
    (currentFolder.children || []).forEach(node => items.push({
      type: "folder", name: node.name, resolution: "—", size: node.video_count, data: node,
    }));
    (currentFolder.videos || []).forEach(v => items.push({
      type: "video", name: v.file_name, resolution: v.resolution, size: v.size_gb, data: v,
    }));
    items.sort((a, b) => {
      // 文件夹始终在前
      if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
      const av = (a as any)[sortKey], bv = (b as any)[sortKey];
      if (typeof av === "number") return sortAsc ? av - bv : bv - av;
      return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    return items;
  }, [currentFolder, sortKey, sortAsc]);

  const totalPages = Math.ceil(rows.length / pageSize);
  const pageRows = rows.slice(page * pageSize, (page + 1) * pageSize);

  if (!currentFolder) return null;

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc); else { setSortKey(key); setSortAsc(true); }
  };

  return (
    <div className="animate-in fade-in duration-200">
      <div className="bg-[#141414] border border-white/[0.06] rounded-xl overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="text-xs text-slate-500 font-medium border-b border-white/[0.06]">
              <th className="px-4 py-3 w-10"></th>
              <th className="px-4 py-3 cursor-pointer hover:text-slate-300" onClick={() => handleSort("name")}>
                名称 {sortKey === "name" && <span className="text-blue-400 ml-1">{sortAsc ? "↑" : "↓"}</span>}
              </th>
              <th className="px-4 py-3 w-28 cursor-pointer hover:text-slate-300" onClick={() => handleSort("resolution")}>分辨率</th>
              <th className="px-4 py-3 w-24 cursor-pointer hover:text-slate-300" onClick={() => handleSort("size")}>大小</th>
              <th className="px-4 py-3 w-32">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.03]">
            {pageRows.map((row, i) => (
              <tr key={i} className={`text-[14px] transition-colors cursor-pointer ${row.type === "video" && selectedPaths.has(row.data.file_path) ? "bg-blue-500/5" : "hover:bg-white/[0.02]"}`}
                onClick={(e) => { e.stopPropagation(); row.type === "folder" ? onFolderDetail(row.data) : onVideoDetail(row.data); }}>
                <td className="px-4 py-2.5">
                  {row.type === "video" && batchMode ? (
                    <input type="checkbox" checked={selectedPaths.has(row.data.file_path)} onChange={() => onToggleSelect(row.data.file_path)}
                      onClick={(e) => e.stopPropagation()}
                      className="w-4 h-4 rounded border-slate-600 bg-transparent checked:bg-blue-500 cursor-pointer" />
                  ) : (
                    <span className="text-base">{row.type === "folder" ? "📂" : ""}</span>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  {row.type === "folder" ? (
                    <button onClick={(e) => { e.stopPropagation(); onFolderDetail(row.data); onNavigate(row.data); }}
                      className="text-left truncate max-w-[500px] block w-full text-blue-400 hover:text-blue-300 font-medium py-1">
                      {row.name}
                    </button>
                  ) : (
                    <span className="text-slate-300 truncate block max-w-[500px]">{row.name}</span>
                  )}
                </td>
                <td className="px-4 py-2.5 text-xs text-slate-500">{row.resolution}</td>
                <td className="px-4 py-2.5 text-xs text-slate-500 font-mono">
                  {row.type === "folder" ? `${row.size} 项` : formatSize(row.size)}
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex gap-1">
                    {row.type === "video" && (
                      <>
                        <button onClick={(e) => { e.stopPropagation(); onPlay(row.data.file_path); }} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">
                          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                        </button>
                        <button onClick={(e) => { e.stopPropagation(); onSearch(row.data.clean_name_cn || row.data.clean_name || row.data.file_name, { cnName: row.data.clean_name_cn || currentFolder?.clean_name_cn, enName: row.data.clean_name_en || currentFolder?.clean_name_en, originalName: row.data.clean_name_original, folderType: currentFolder?.folder_type, savePath: currentFolder?.path }); }} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-blue-400 hover:bg-blue-500/10 transition-all">
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" /></svg>
                        </button>
                      </>
                    )}
                    <button onClick={(e) => { e.stopPropagation(); row.type === "folder" ? onFolderDetail(row.data) : onVideoDetail(row.data); }}
                      className="text-xs text-slate-500 hover:text-blue-400 px-2 py-1 rounded transition-all">详情</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* 翻页 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 px-2">
          <span className="text-xs text-slate-500">{rows.length} 项 · 第 {page + 1}/{totalPages} 页</span>
          <div className="flex gap-1">
            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
              className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-all">上一页</button>
            <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
              className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-all">下一页</button>
          </div>
        </div>
      )}
    </div>
  );
}
