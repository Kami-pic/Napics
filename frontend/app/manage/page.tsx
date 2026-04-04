// 批处理管理页面 — 独立页面，全库表格 + 筛选 + 翻页
"use client";
import { useState, useEffect, useMemo } from "react";
import type { VideoInfo, FilterType } from "@/types";
import { api } from "@/lib/api";
import { formatSize } from "@/lib/utils";
import Link from "next/link";

type SortKey = "file_name" | "folder_name" | "resolution" | "size_gb" | "subtitle_count" | "hdr_type" | "audio_codec" | "has_nfo" | "shadow_name";

const _hasEnglish = (s: string) => /[a-zA-Z]{3,}/.test(s);
const _hasJpKr = (s: string) => /[\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]/.test(s);
const _isBadShadow = (v: VideoInfo) => {
  const sn = v.shadow_name || "";
  if (!sn) return true;  // 无影子名
  return !_hasEnglish(sn);  // 没有英文
};

export default function ManagePage() {
  const [videos, setVideos] = useState<VideoInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [sortKey, setSortKey] = useState<SortKey>("file_name");
  const [sortAsc, setSortAsc] = useState(true);
  const [searchText, setSearchText] = useState("");
  const [filter, setFilter] = useState<FilterType | "no_nfo" | "bad_shadow">("all");
  const [moveTarget, setMoveTarget] = useState("");
  const [page, setPage] = useState(0);
  const [scraping, setScraping] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [batchProgress, setBatchProgress] = useState("");
  const pageSize = 100;

  const refresh = async () => {
    const data = await api.getLibrary();
    setVideos(data);
  };

  useEffect(() => {
    api.getLibrary().then(data => { setVideos(data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc); else { setSortKey(key); setSortAsc(true); }
  };

  const toggleSelect = (path: string) => {
    setSelectedPaths(prev => { const n = new Set(prev); if (n.has(path)) n.delete(path); else n.add(path); return n; });
  };

  const filterCounts = useMemo(() => ({
    all: videos.length,
    upgrade: videos.filter(v => v.is_low_res).length,
    nosub: videos.filter(v => v.subtitle_count === 0).length,
    dolby: videos.filter(v => v.audio_codec?.toLowerCase().includes("ac3") || v.audio_codec?.toLowerCase().includes("dts")).length,
    hdr: videos.filter(v => v.hdr_type !== "SDR").length,
    large: videos.filter(v => v.size_gb >= 10).length,
    small: videos.filter(v => v.size_gb < 1).length,
    no_nfo: videos.filter(v => !v.has_nfo).length,
    bad_shadow: videos.filter(v => _isBadShadow(v)).length,
  }), [videos]);

  const sorted = useMemo(() => {
    let data = [...videos];
    if (filter === "upgrade") data = data.filter(v => v.is_low_res);
    else if (filter === "nosub") data = data.filter(v => v.subtitle_count === 0);
    else if (filter === "dolby") data = data.filter(v => v.audio_codec?.toLowerCase().includes("ac3") || v.audio_codec?.toLowerCase().includes("dts"));
    else if (filter === "hdr" as any) data = data.filter(v => v.hdr_type !== "SDR");
    else if (filter === "large" as any) data = data.filter(v => v.size_gb >= 10);
    else if (filter === "small" as any) data = data.filter(v => v.size_gb < 1);
    else if (filter === "no_nfo") data = data.filter(v => !v.has_nfo);
    else if (filter === "bad_shadow") data = data.filter(v => _isBadShadow(v));
    if (searchText) {
      const q = searchText.toLowerCase();
      data = data.filter(v => v.file_name.toLowerCase().includes(q) || v.folder_name.toLowerCase().includes(q));
    }
    data.sort((a, b) => {
      const av = (a as any)[sortKey], bv = (b as any)[sortKey];
      if (typeof av === "number") return sortAsc ? av - bv : bv - av;
      return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    return data;
  }, [videos, sortKey, sortAsc, searchText, filter]);

  const totalPages = Math.ceil(sorted.length / pageSize);
  const pageRows = sorted.slice(page * pageSize, (page + 1) * pageSize);
  const selCount = selectedPaths.size;

  // 全选当前筛选结果（不只是当前页）
  const selectAllFiltered = () => {
    const allSel = sorted.every(v => selectedPaths.has(v.file_path));
    const n = new Set(selectedPaths);
    sorted.forEach(v => allSel ? n.delete(v.file_path) : n.add(v.file_path));
    setSelectedPaths(n);
  };

  const handleBatch = async (action: "delete" | "move" | "copy") => {
    const label = action === "delete" ? "删除" : action === "move" ? "移动" : "复制";
    if (action === "delete" && !confirm(`确定要批量删除 ${selCount} 个文件吗？`)) return;
    if ((action === "move" || action === "copy") && !moveTarget) { alert("请输入目标路径"); return; }
    try {
      await api.batchManage(action, Array.from(selectedPaths), moveTarget || undefined);
      alert(`${label}完成`);
      setSelectedPaths(new Set());
      await refresh();
    } catch { alert("失败"); }
  };

  const handleBatchScrape = async () => {
    setScraping(true); setBatchProgress("批量刮削中...");
    try {
      const paths = Array.from(selectedPaths);
      for (let i = 0; i < paths.length; i++) {
        const name = paths[i].split(/[/\\]/).pop() || "";
        setBatchProgress(`刮削中 (${i + 1}/${paths.length}) ${name}`);
        try { await api.executeScrape(paths[i]); } catch {}
      }
      setBatchProgress("");
      alert(`刮削完成：${paths.length} 项`);
      await refresh();
    } catch { alert("刮削失败"); setBatchProgress(""); }
    setScraping(false);
  };

  // 批量改名：默认只存影子名
  const handleBatchRename = async () => {
    setRenaming(true); setBatchProgress("批量生成标准名...");
    try {
      const folders = new Set<string>();
      for (const fp of selectedPaths) {
        const sep = fp.lastIndexOf("\\") !== -1 ? "\\" : "/";
        folders.add(fp.substring(0, fp.lastIndexOf(sep)));
      }
      const folderList = Array.from(folders);
      let total = 0;
      for (let i = 0; i < folderList.length; i++) {
        const folder = folderList[i];
        const folderName = folder.split(/[/\\]/).pop() || folder;
        setBatchProgress(`生成标准名 (${i + 1}/${folderList.length}) ${folderName}`);
        const r = await api.renameVideos(folder, false, true);
        total += r.filled || r.shadow_filled || 0;
      }
      setBatchProgress("");
      alert(`标准名生成完成：${total} 项`);
      await refresh();
    } catch { alert("生成失败"); setBatchProgress(""); }
    setRenaming(false);
  };

  // 标准名覆盖真名：把已有标准名写入文件名
  const handleShadowToReal = async () => {
    if (!confirm(`确定要将 ${selCount} 个文件的标准名覆盖为真实文件名吗？此操作会修改文件名。`)) return;
    setRenaming(true); setBatchProgress("覆盖文件名...");
    try {
      const folders = new Set<string>();
      for (const fp of selectedPaths) {
        const sep = fp.lastIndexOf("\\") !== -1 ? "\\" : "/";
        folders.add(fp.substring(0, fp.lastIndexOf(sep)));
      }
      const folderList = Array.from(folders);
      let total = 0;
      for (let i = 0; i < folderList.length; i++) {
        const folder = folderList[i];
        const folderName = folder.split(/[/\\]/).pop() || folder;
        setBatchProgress(`改名 (${i + 1}/${folderList.length}) ${folderName}`);
        const r = await api.renameVideos(folder, false, false);
        total += r.items?.length || 0;
      }
      setBatchProgress("");
      alert(`改名完成：${total} 项`);
      setSelectedPaths(new Set());
      await refresh();
    } catch { alert("改名失败"); setBatchProgress(""); }
    setRenaming(false);
  };

  return (
    <main className="min-h-screen bg-[#0f0f0f] text-white">
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-slate-500 hover:text-white transition-colors text-sm">← 返回媒体库</Link>
            <h1 className="text-xl font-semibold text-slate-200">批处理管理</h1>
            <span className="text-sm text-slate-500">全库 {videos.length} · 匹配 {sorted.length} · 已选 {selCount}</span>
          </div>
          <button onClick={selectAllFiltered} className="px-4 py-1.5 rounded-lg bg-white/[0.06] text-xs text-slate-300 hover:bg-white/10">
            {sorted.every(v => selectedPaths.has(v.file_path)) && sorted.length > 0 ? "取消全选" : `全选筛选结果 (${sorted.length})`}
          </button>
        </div>

        {/* 工具栏 */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <input value={searchText} onChange={e => { setSearchText(e.target.value); setPage(0); }} placeholder="搜索文件名或路径..."
            className="bg-white/[0.04] border border-white/[0.06] rounded-lg px-4 py-2 text-sm w-72 focus:ring-1 focus:ring-blue-500/30 outline-none text-slate-300" />
          <div className="flex gap-1 flex-wrap">
            {([
              ["all", "全部", filterCounts.all],
              ["upgrade", "低画质", filterCounts.upgrade],
              ["nosub", "缺字幕", filterCounts.nosub],
              ["no_nfo", "未刮削", filterCounts.no_nfo],
              ["bad_shadow", "标准名异常", filterCounts.bad_shadow],
              ["dolby", "杜比/DTS", filterCounts.dolby],
              ["hdr", "HDR/DV", filterCounts.hdr],
              ["large", "≥10G", filterCounts.large],
              ["small", "<1G", filterCounts.small],
            ] as [string, string, number][]).map(([id, label, count]) => (
              <button key={id} onClick={() => { setFilter(id as any); setPage(0); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${filter === id ? "bg-blue-500/20 text-blue-400" : "text-slate-500 hover:text-slate-300 hover:bg-white/5"}`}>
                {label}
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${filter === id ? "bg-blue-500/30 text-blue-300" : "bg-white/[0.06] text-slate-600"}`}>{count}</span>
              </button>
            ))}
          </div>
        </div>

        {/* 批量操作栏 */}
        {selCount > 0 && (
          <div className="flex flex-wrap items-center gap-2 mb-4 p-3 bg-blue-500/5 border border-blue-500/10 rounded-xl">
            <span className="text-xs text-blue-400 mr-2">已选 {selCount} 项</span>
            <input value={moveTarget} onChange={e => setMoveTarget(e.target.value)} placeholder="目标路径（移动/复制用）"
              className="bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-1.5 text-xs w-52 outline-none text-slate-400" />
            <button onClick={() => handleBatch("move")} className="px-3 py-1.5 rounded-lg bg-blue-500/20 text-blue-400 text-xs hover:bg-blue-500/30">移动</button>
            <button onClick={() => handleBatch("copy")} className="px-3 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-400 text-xs hover:bg-cyan-500/30">复制</button>
            <button onClick={() => handleBatch("delete")} className="px-3 py-1.5 rounded-lg bg-red-500/20 text-red-400 text-xs hover:bg-red-500/30">删除</button>
            <div className="w-px h-5 bg-white/10" />
            <button onClick={handleBatchScrape} disabled={scraping} className="px-3 py-1.5 rounded-lg bg-purple-500/20 text-purple-400 text-xs hover:bg-purple-500/30 disabled:opacity-50">
              {scraping ? "刮削中..." : "批量刮削"}
            </button>
            <button onClick={handleBatchRename} disabled={renaming} className="px-3 py-1.5 rounded-lg bg-green-500/20 text-green-400 text-xs hover:bg-green-500/30 disabled:opacity-50">
              {renaming ? "处理中..." : "批量生成标准名"}
            </button>
            <button onClick={handleShadowToReal} disabled={renaming} className="px-3 py-1.5 rounded-lg bg-amber-500/20 text-amber-400 text-xs hover:bg-amber-500/30 disabled:opacity-50">
              {renaming ? "处理中..." : "标准名覆盖真名"}
            </button>
            <div className="w-px h-5 bg-white/10" />
            <button onClick={() => setSelectedPaths(new Set())} className="text-xs text-slate-500 hover:text-slate-300 px-2">清空选择</button>
            {batchProgress && (
              <div className="w-full mt-2 flex items-center gap-2 py-2 px-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                <span className="text-xs text-blue-400 truncate">{batchProgress}</span>
              </div>
            )}
          </div>
        )}

        {/* 表格 */}
        {loading ? (
          <div className="flex items-center justify-center h-64 text-slate-500">加载中...</div>
        ) : (
          <div className="bg-[#141414] border border-white/[0.06] rounded-xl overflow-hidden">
            <table className="w-full text-left">
              <thead className="sticky top-0 bg-[#141414] z-10">
                <tr className="text-xs text-slate-500 font-medium border-b border-white/[0.06]">
                  <th className="px-4 py-3 w-10">
                    <input type="checkbox"
                      checked={pageRows.length > 0 && pageRows.every(v => selectedPaths.has(v.file_path))}
                      onChange={() => {
                        const allSel = pageRows.every(v => selectedPaths.has(v.file_path));
                        const n = new Set(selectedPaths);
                        pageRows.forEach(v => allSel ? n.delete(v.file_path) : n.add(v.file_path));
                        setSelectedPaths(n);
                      }} className="w-4 h-4 rounded border-slate-600 bg-transparent" />
                  </th>
                  {([["file_name","文件名"],["folder_name","文件夹"],["resolution","分辨率"],["audio_codec","音频"],["size_gb","大小"],["subtitle_count","字幕"],["hdr_type","HDR"],["has_nfo","刮削"],["shadow_name","标准名"]] as [SortKey, string][]).map(([key, label]) => (
                    <th key={key} onClick={() => handleSort(key)} className="px-4 py-3 cursor-pointer hover:text-slate-300 transition-colors">
                      {label} {sortKey === key && <span className="text-blue-400 ml-1">{sortAsc ? "↑" : "↓"}</span>}
                    </th>
                  ))}
                  <th className="px-4 py-3 w-20">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.03]">
                {pageRows.map((v, idx) => {
                  const sel = selectedPaths.has(v.file_path);
                  return (
                    <tr key={idx} className={`text-[14px] transition-colors ${sel ? "bg-blue-500/5" : "hover:bg-white/[0.02]"}`}>
                      <td className="px-4 py-2.5"><input type="checkbox" checked={sel} onChange={() => toggleSelect(v.file_path)} className="w-4 h-4 rounded border-slate-600 bg-transparent checked:bg-blue-500 cursor-pointer" /></td>
                      <td className="px-4 py-2.5 text-slate-300 max-w-[300px] truncate">{v.file_name}</td>
                      <td className="px-4 py-2.5 text-slate-500 max-w-[140px] truncate text-xs">{v.folder_name}</td>
                      <td className={`px-4 py-2.5 text-xs ${v.is_low_res ? "text-orange-400" : "text-slate-400"}`}>{v.resolution}</td>
                      <td className="px-4 py-2.5 text-xs text-slate-400">{v.audio_codec || "—"}</td>
                      <td className="px-4 py-2.5 text-xs text-slate-400 font-mono">{formatSize(v.size_gb)}</td>
                      <td className="px-4 py-2.5 text-xs">{v.subtitle_count > 0 ? <span className="text-green-400/70">{v.subtitle_count}</span> : <span className="text-slate-700">—</span>}</td>
                      <td className="px-4 py-2.5 text-xs">{v.hdr_type !== "SDR" ? <span className="text-purple-400">{v.hdr_type}</span> : <span className="text-slate-700">SDR</span>}</td>
                      <td className="px-4 py-2.5 text-xs">{v.has_nfo ? <span className="text-green-400/70">✓</span> : <span className="text-slate-700">—</span>}</td>
                      <td className="px-4 py-2.5 text-xs max-w-[160px]">
                        <ShadowCell filePath={v.file_path} value={v.shadow_name || ""} isBad={_isBadShadow(v)} onSaved={refresh} />
                      </td>
                      <td className="px-4 py-2.5">
                        <button onClick={() => api.play(v.file_path)} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">
                          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* 翻页 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-4 px-1">
            <span className="text-xs text-slate-500">第 {page + 1}/{totalPages} 页 · 每页 {pageSize} 条</span>
            <div className="flex gap-1">
              <button onClick={() => setPage(0)} disabled={page === 0} className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:bg-white/5 disabled:opacity-30">首页</button>
              <button onClick={() => setPage(p => p - 1)} disabled={page === 0} className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:bg-white/5 disabled:opacity-30">上一页</button>
              <button onClick={() => setPage(p => p + 1)} disabled={page >= totalPages - 1} className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:bg-white/5 disabled:opacity-30">下一页</button>
              <button onClick={() => setPage(totalPages - 1)} disabled={page >= totalPages - 1} className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:bg-white/5 disabled:opacity-30">末页</button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

function ShadowCell({ filePath, value, isBad, onSaved }: { filePath: string; value: string; isBad: boolean; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [editVal, setEditVal] = useState(value);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    const trimmed = editVal.trim();
    if (trimmed === value) { setEditing(false); return; }
    setSaving(true);
    try {
      if (trimmed) {
        await api.setShadowName(filePath, trimmed, "manual");
      } else {
        await api.clearShadowName(filePath);
      }
      onSaved();
      setEditing(false);
    } catch { alert("保存失败"); }
    setSaving(false);
  };

  if (editing) {
    return (
      <div className="flex gap-1" onClick={e => e.stopPropagation()}>
        <input value={editVal} onChange={e => setEditVal(e.target.value)} autoFocus
          onKeyDown={e => { if (e.key === "Enter") handleSave(); if (e.key === "Escape") setEditing(false); }}
          className="flex-1 bg-white/[0.06] border border-white/[0.08] rounded px-1.5 py-0.5 text-xs text-white outline-none focus:border-blue-500/40 min-w-[100px]" />
        <button onClick={handleSave} disabled={saving} className="text-[10px] text-blue-400 flex-shrink-0">{saving ? "..." : "✓"}</button>
        <button onClick={() => setEditing(false)} className="text-[10px] text-slate-600 flex-shrink-0">✕</button>
      </div>
    );
  }

  return (
    <span className={`truncate block cursor-pointer hover:underline ${isBad ? "text-orange-400" : value ? "text-blue-400/70" : "text-slate-700"}`}
      title={value || "点击设置"}
      onClick={e => { e.stopPropagation(); setEditVal(value); setEditing(true); }}>
      {value || "—"}
    </span>
  );
}
