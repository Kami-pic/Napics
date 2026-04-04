// 整理历史记录面板
"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { OrganizeHistorySnapshot } from "@/types";

interface Props {
  open: boolean;
  onClose: () => void;
  onRefresh: () => void;
}

export default function OrganizeHistory({ open, onClose, onRefresh }: Props) {
  const [snapshots, setSnapshots] = useState<OrganizeHistorySnapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [rolling, setRolling] = useState(false);

  useEffect(() => {
    if (open) loadHistory();
  }, [open]);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const r = await api.getOrganizeHistory(50);
      setSnapshots(r.snapshots || []);
    } catch { /* silent */ }
    setLoading(false);
  };

  const handleRollback = async (id: number) => {
    if (!confirm("确定回滚这次整理操作？文件将恢复到操作前的位置。")) return;
    setRolling(true);
    try {
      await api.rollbackRename(id);
      await loadHistory();
      onRefresh();
    } catch {
      alert("回滚失败");
    }
    setRolling(false);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-8 z-50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-[var(--background)] border border-white/[0.06] rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-white/[0.06]">
          <h2 className="text-base font-semibold text-white">整理历史记录</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-lg">✕</button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2 no-scrollbar">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-5 h-5 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin" />
            </div>
          ) : snapshots.length === 0 ? (
            <p className="text-center text-slate-600 text-sm py-12">暂无整理记录</p>
          ) : (
            snapshots.map(s => (
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
                    {s.ops.map((op, i) => (
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
      </div>
    </div>
  );
}
