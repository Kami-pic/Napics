// 操作历史面板：整理记录（可回滚）+ 回收站（可恢复/清理）合并
"use client";
import { useState, useEffect, useCallback } from "react";
import type { RecycleBinEntry } from "@/types";
import { api } from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
  onRefresh: () => void;
}

type Tab = "history" | "recycle";

export default function OperationHistory({ open, onClose, onRefresh }: Props) {
  const [tab, setTab] = useState<Tab>("history");

  // ── 整理记录 ──
  const [snapshots, setSnapshots] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [rolling, setRolling] = useState(false);

  // ── 回收站 ──
  const [entries, setEntries] = useState<RecycleBinEntry[]>([]);
  const [recycleLoading, setRecycleLoading] = useState(false);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [cleaning, setCleaning] = useState(false);
  const [confirmRestore, setConfirmRestore] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const r = await api.getOrganizeHistory(50);
      setSnapshots(r.snapshots || []);
    } catch { /* silent */ }
    setHistoryLoading(false);
  }, []);

  const loadRecycle = useCallback(async () => {
    setRecycleLoading(true);
    try {
      const d = await api.getRecycleBin();
      setEntries(d.entries || []);
    } catch { /* silent */ }
    setRecycleLoading(false);
  }, []);

  useEffect(() => {
    if (!open) return;
    if (tab === "history") loadHistory();
    else loadRecycle();
  }, [open, tab, loadHistory, loadRecycle]);

  const handleRollback = async (id: number) => {
    if (!confirm("确定回滚？文件将恢复到操作前的位置和名称。")) return;
    setRolling(true);
    try {
      await api.rollbackRename(id);
      await loadHistory();
      onRefresh();
    } catch { alert("回滚失败"); }
    setRolling(false);
  };

  const handleRestore = async (entryId: string) => {
    setRestoringId(entryId);
    try {
      await api.restoreFromBin(entryId);
      await loadRecycle();
      onRefresh();
    } catch { alert("恢复失败"); }
    setRestoringId(null);
    setConfirmRestore(null);
  };

  const handleCleanup = async () => {
    setCleaning(true);
    try {
      await api.cleanupRecycleBin();
      await loadRecycle();
    } catch { alert("清理失败"); }
    setCleaning(false);
  };

  if (!open) return null;

  const totalSize = entries.reduce((sum, e) => sum + e.size_gb, 0);

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-8 z-50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-[#141414] border border-white/[0.06] rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* 顶栏 */}
        <div className="flex items-center justify-between p-5 border-b border-white/[0.06]">
          <h2 className="text-base font-semibold text-white">操作历史</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-lg">✕</button>
        </div>

        {/* Tab 切换 */}
        <div className="flex border-b border-white/[0.06]">
          <button onClick={() => setTab("history")}
            className={`flex-1 py-2.5 text-xs font-medium transition-colors ${tab === "history" ? "text-blue-400 border-b-2 border-blue-400" : "text-slate-500 hover:text-slate-300"}`}>
            整理记录 {snapshots.length > 0 && <span className="ml-1 text-slate-600">({snapshots.length})</span>}
          </button>
          <button onClick={() => setTab("recycle")}
            className={`flex-1 py-2.5 text-xs font-medium transition-colors ${tab === "recycle" ? "text-blue-400 border-b-2 border-blue-400" : "text-slate-500 hover:text-slate-300"}`}>
            回收站 {entries.length > 0 && <span className="ml-1 text-slate-600">({entries.length} · {totalSize.toFixed(1)}GB)</span>}
          </button>
        </div>

        {/* 内容区 */}
        <div className="flex-1 overflow-y-auto p-4 no-scrollbar">
          {/* ── 整理记录 Tab ── */}
          {tab === "history" && (
            <div className="space-y-2">
              {historyLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="w-5 h-5 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin" />
                </div>
              ) : snapshots.length === 0 ? (
                <p className="text-center text-slate-600 text-sm py-12">暂无整理记录</p>
              ) : (
                snapshots.map((s: any) => (
                  <div key={s.id} className="bg-white/[0.02] border border-white/[0.06] rounded-lg">
                    <div className="flex items-center justify-between p-3 cursor-pointer hover:bg-white/[0.02]"
                      onClick={() => setExpandedId(expandedId === s.id ? null : s.id)}>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-slate-500">{s.time}</span>
                        {s.label && <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/10 text-blue-400">{s.label}</span>}
                        <span className="text-xs text-slate-400">{s.ops?.length || 0} 项操作</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleRollback(s.id); }}
                          disabled={rolling}
                          className="text-[10px] px-2 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 disabled:opacity-50"
                        >
                          回滚
                        </button>
                        <span className="text-slate-600 text-xs">{expandedId === s.id ? "▲" : "▼"}</span>
                      </div>
                    </div>
                    {expandedId === s.id && s.ops && (
                      <div className="border-t border-white/[0.04] p-3 space-y-1 max-h-60 overflow-y-auto">
                        {s.ops.map((op: any, i: number) => (
                          <div key={i} className="text-[10px] text-slate-500 font-mono flex gap-2">
                            <span className="text-slate-600 shrink-0">{op.is_dir ? "📁" : "📄"}</span>
                            <span className="text-red-400/60 truncate">{op.old_path.split(/[/\\]/).pop()}</span>
                            <span className="text-slate-700">→</span>
                            <span className="text-green-400/60 truncate">{op.new_path.split(/[/\\]/).pop()}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {/* ── 回收站 Tab ── */}
          {tab === "recycle" && (
            <div className="space-y-2">
              {/* 清理按钮 */}
              {entries.length > 0 && (
                <div className="flex justify-end mb-2">
                  <button onClick={handleCleanup} disabled={cleaning}
                    className="px-3 py-1.5 rounded-lg text-[11px] bg-red-600/20 text-red-400 hover:bg-red-600/30 transition-colors disabled:opacity-40">
                    {cleaning ? "清理中..." : "清理过期文件"}
                  </button>
                </div>
              )}
              {recycleLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="w-5 h-5 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin" />
                </div>
              ) : entries.length === 0 ? (
                <p className="text-center text-slate-600 text-sm py-12">回收站为空</p>
              ) : (
                entries.map(entry => {
                  const fileName = entry.original_path.split(/[/\\]/).pop() || entry.original_path;
                  const movedDate = entry.moved_at ? new Date(entry.moved_at).toLocaleString("zh-CN") : "";
                  const expiresDate = entry.expires_at ? new Date(entry.expires_at).toLocaleDateString("zh-CN") : "";
                  const isConfirming = confirmRestore === entry.id;

                  return (
                    <div key={entry.id} className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-3.5 space-y-1.5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-white font-medium truncate" title={fileName}>{fileName}</p>
                          <p className="text-[10px] text-slate-500 truncate mt-0.5" title={entry.original_path}>
                            {entry.original_path}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <span className="text-[10px] text-slate-500">{entry.size_gb} GB</span>
                          {isConfirming ? (
                            <div className="flex gap-1">
                              <button onClick={() => handleRestore(entry.id)} disabled={restoringId === entry.id}
                                className="px-2 py-1 rounded text-[10px] bg-green-600 text-white hover:bg-green-500 disabled:opacity-50">
                                {restoringId === entry.id ? "..." : "确定"}
                              </button>
                              <button onClick={() => setConfirmRestore(null)}
                                className="px-2 py-1 rounded text-[10px] bg-white/[0.04] text-slate-400 hover:text-white">
                                取消
                              </button>
                            </div>
                          ) : (
                            <button onClick={() => setConfirmRestore(entry.id)}
                              className="px-2.5 py-1 rounded-lg text-[10px] bg-white/[0.04] text-slate-400 hover:text-green-400 hover:bg-green-500/10 transition-colors">
                              恢复
                            </button>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-4 text-[10px] text-slate-600">
                        <span>{movedDate}</span>
                        <span>过期 {expiresDate}</span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
