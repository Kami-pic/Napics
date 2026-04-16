// 新增影片 — BT 资源搜索弹窗（从发现页点击"搜索资源"打开）
"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import type { EnhancedSearchResult, FilterState, AddMediaInfo } from "@/types";
import { api } from "@/lib/api";
import FilterBar, { DEFAULT_FILTERS, applyFilters } from "../search/FilterBar";

interface AddMediaPanelProps {
  open: boolean;
  onClose: () => void;
  onRefresh: () => void;
  defaultSavePath: string;
  qbConfigured: boolean;
  alistConfigured: boolean;
  initialQuery?: string;
}

export default function AddMediaPanel({
  open, onClose, onRefresh, defaultSavePath,
  qbConfigured, alistConfigured, initialQuery = "",
}: AddMediaPanelProps) {
  const [keyword, setKeyword] = useState(initialQuery);
  const [results, setResults] = useState<EnhancedSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [savePath, setSavePath] = useState(defaultSavePath);
  const [downloadChannel, setDownloadChannel] = useState<"qb" | "alist">(qbConfigured ? "qb" : "alist");
  const [downloadingUrl, setDownloadingUrl] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    if (open) {
      setKeyword(initialQuery);
      setSavePath(defaultSavePath);
      setToast(null);
      if (initialQuery) doSearch(initialQuery);
    }
    if (!open) {
      setResults([]); setError(""); setToast(null);
      setFilters(DEFAULT_FILTERS); setDownloadingUrl(null);
      if (closeTimer.current) clearTimeout(closeTimer.current);
    }
  }, [open, initialQuery]);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setSearching(true); setResults([]); setError(""); setToast(null);
    try {
      const data = await api.search(q);
      const raw: EnhancedSearchResult[] = (data.bt_results || []).map((r: any) => ({
        ...r,
        quality: r.quality || { resolution: "", source: "", video_codec: "", audio_codec: "", has_chinese_sub: false, display: r.quality_tag || "" },
        quality_rank: r.quality_rank ?? 0,
      }));
      raw.sort((a, b) => b.seeders - a.seeders);
      setResults(raw);
    } catch { setError("搜索失败，请检查 Prowlarr 配置"); }
    finally { setSearching(false); }
  }, []);

  const handleDownload = async (res: EnhancedSearchResult) => {
    setDownloadingUrl(res.download_url); setToast(null);
    try {
      const d = await api.download(res.download_url, savePath, downloadChannel);
      if (d.success) {
        setToast({ msg: "任务已下达", ok: true });
        onRefresh();
        closeTimer.current = setTimeout(() => onClose(), 3000);
      } else {
        setToast({ msg: "失败: " + (d.message || "未知错误"), ok: false });
      }
    } catch { setToast({ msg: "通信失败", ok: false }); }
    finally { setDownloadingUrl(null); }
  };

  const filtered = applyFilters(results, filters);
  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-8 z-50"
      onClick={(e) => { e.stopPropagation(); if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-[var(--background)] border border-white/[0.06] rounded-2xl w-full max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
        {/* 顶栏 */}
        <div className="p-5 border-b border-white/[0.06] space-y-3">
          <div className="flex justify-between items-center">
            <h2 className="text-[15px] font-bold text-white">搜索资源</h2>
            <button onClick={onClose} className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">✕</button>
          </div>
          <div className="flex gap-2">
            <input value={keyword} onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && doSearch(keyword)}
              placeholder="输入搜索关键词..."
              className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-blue-500/50 placeholder:text-slate-600" />
            <button onClick={() => doSearch(keyword)} disabled={searching}
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-medium disabled:opacity-50 transition-colors">
              {searching ? "搜索中..." : "搜索"}
            </button>
          </div>
          <FilterBar filters={filters} onChange={setFilters} onClear={() => setFilters(DEFAULT_FILTERS)} btSources={[]} sourceStatuses={{}} disabledSources={new Set()} onToggleSource={() => {}} />
        </div>

        {/* Toast */}
        {toast && (
          <div className={`mx-5 mt-3 px-4 py-2 rounded-lg text-xs ${
            toast.ok ? "bg-green-500/10 text-green-400 border border-green-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"
          }`}>{toast.msg}</div>
        )}

        {/* 结果 */}
        <div className="flex-1 overflow-y-auto p-5">
          {searching ? (
            <div className="flex flex-col items-center py-16">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mb-3" />
              <p className="text-xs text-slate-500">搜罗全网资源...</p>
            </div>
          ) : error ? (
            <div className="text-center py-10">
              <p className="text-red-400 text-xs mb-3">{error}</p>
              <button onClick={() => doSearch(keyword)} className="text-xs text-blue-400 hover:text-blue-300">重试</button>
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.length > 0 && (
                <p className="text-[10px] text-slate-600 mb-2">共 {results.length} 条{filtered.length !== results.length ? `，筛选后 ${filtered.length} 条` : ""}</p>
              )}
              {filtered.map((res, i) => {
                const isDownloading = downloadingUrl === res.download_url;
                return (
                  <div key={i} className="bg-white/[0.02] p-3.5 rounded-xl border border-white/[0.04] hover:border-white/[0.08] transition-colors">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="font-bold text-xs text-slate-400">{res.quality?.display || res.quality_tag}</span>
                          <span className="text-[10px] text-slate-600">{res.indexer}</span>
                          {res.quality?.has_chinese_sub && <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">中字</span>}
                        </div>
                        <p className="text-[11px] text-slate-500 truncate" title={res.title}>{res.title}</p>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0">
                        <div className="text-right">
                          <p className="font-bold text-xs text-slate-300">{res.size_gb} GB</p>
                          <p className="text-[10px] text-slate-600">做种 {res.seeders}</p>
                        </div>
                        <button onClick={() => handleDownload(res)}
                          disabled={isDownloading || (!qbConfigured && downloadChannel === "qb") || (!alistConfigured && downloadChannel === "alist")}
                          className="px-3 py-1.5 rounded-lg text-xs font-bold bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
                          {isDownloading ? "..." : "下载"}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
              {filtered.length === 0 && results.length > 0 && (
                <p className="text-center py-10 text-xs text-slate-600">无匹配筛选条件的结果</p>
              )}
              {results.length === 0 && !searching && !error && (
                <p className="text-center py-10 text-xs text-slate-600">未搜到资源</p>
              )}
            </div>
          )}
        </div>

        {/* 底部操作栏 */}
        <div className="p-4 border-t border-white/[0.06] flex items-center gap-3">
          <span className="text-[10px] text-slate-600">保存到：</span>
          <input value={savePath} onChange={(e) => setSavePath(e.target.value)}
            className="bg-white/[0.04] border border-white/[0.06] rounded-lg px-2 py-1.5 text-[11px] text-white outline-none focus:border-blue-500/50 w-48" />
          <div className="w-px h-5 bg-white/[0.06]" />
          <span className="text-[10px] text-slate-600">通道：</span>
          <div className="flex gap-1">
            <button onClick={() => setDownloadChannel("qb")} disabled={!qbConfigured}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition-colors ${
                downloadChannel === "qb" && qbConfigured ? "bg-blue-600 text-white" : qbConfigured ? "bg-white/[0.06] text-slate-400 hover:bg-white/10" : "bg-white/[0.04] text-slate-600 cursor-not-allowed"
              }`}>qB</button>
            <button onClick={() => setDownloadChannel("alist")} disabled={!alistConfigured}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition-colors ${
                downloadChannel === "alist" && alistConfigured ? "bg-emerald-600 text-white" : alistConfigured ? "bg-white/[0.06] text-slate-400 hover:bg-white/10" : "bg-white/[0.04] text-slate-600 cursor-not-allowed"
              }`}>Alist</button>
          </div>
        </div>
      </div>
    </div>
  );
}
