// 回收站面板：列出被替换的旧文件，支持恢复和清理
"use client";
import { useState, useEffect, useCallback } from "react";
import type { RecycleBinEntry } from "@/types";
import { api } from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function RecycleBinPanel({ open, onClose }: Props) {
  const [entries, setEntries] = useState<RecycleBinEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [cleaning, setCleaning] = useState(false);
  const [confirmRestore, setConfirmRestore] = useState<string | null>(null);

  const loadEntries = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api.getRecycleBin();
      setEntries(d.entries || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { if (open) loadEntries(); }, [open, loadEntries]);

  const handleRestore = async (entryId: string) => {
    setRestoringId(entryId);
    try {
      await api.restoreFromBin(entryId);
      loadEntries();
    } catch { /* ignore */ }
    setRestoringId(null);
    setConfirmRestore(null);
  };

  const handleCleanup = async () => {
    setCleaning(true);
    try {
      const d = await api.cleanupRecycleBin();
      loadEntries();
    } catch { /* ignore */ }
    setCleaning(false);
  };

  const totalSize = entries.reduce((sum, e) => sum + e.size_gb, 0);

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-6 z-50">
      <div className="bg-[#141414] border border-white/[0.06] rounded-2xl w-full max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
        {/* 顶栏 */}
        <div className="p-5 border-b border-white/[0.06] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-[15px] font-bold text-white">🗑️ 回收站</h2>
            <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.06] text-slate-400">
              {entries.length} 个文件 · {totalSize.toFixed(1)} GB
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={handleCleanup} disabled={cleaning || entries.length === 0}
              className="px-3 py-1.5 rounded-lg text-[11px] bg-red-600/20 text-red-400 hover:bg-red-600/30 transition-colors disabled:opacity-40">
              {cleaning ? "清理中..." : "清理过期"}
            </button>
            <button onClick={onClose} className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10">✕</button>
          </div>
        </div>

        {/* 文件列表 */}
        <div className="flex-1 overflow-y-auto p-5 space-y-2">
          {loading && <p className="text-center py-10 text-xs text-slate-500">加载中...</p>}
          {!loading && entries.length === 0 && (
            <p className="text-center py-16 text-xs text-slate-600">回收站为空</p>
          )}
          {entries.map(entry => {
            const fileName = entry.original_path.split(/[/\\]/).pop() || entry.original_path;
            const movedDate = entry.moved_at ? new Date(entry.moved_at).toLocaleString("zh-CN") : "";
            const expiresDate = entry.expires_at ? new Date(entry.expires_at).toLocaleDateString("zh-CN") : "";
            const isConfirming = confirmRestore === entry.id;

            return (
              <div key={entry.id} className="bg-[#1a1a1a] rounded-xl border border-white/[0.04] p-3.5 space-y-1.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-white font-medium truncate" title={fileName}>{fileName}</p>
                    <p className="text-[10px] text-slate-500 truncate mt-0.5" title={entry.original_path}>
                      原始路径：{entry.original_path}
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
                  <span>移入时间：{movedDate}</span>
                  <span>过期时间：{expiresDate}</span>
                  {entry.task_id && <span>任务：{entry.task_id}</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
