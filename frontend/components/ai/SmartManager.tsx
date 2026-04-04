// 智能管理中枢 — 整合 AI 建议、手动批量、历史回滚
"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { AISuggestion, OrganizeSnapshot } from "@/types";

interface SmartManagerProps {
  selectedCount: number;
  selectedPaths: string[];
  onClearSelection: () => void;
  onRefresh: () => void;
  batchAction: (action: "delete" | "move", targetDir?: string) => void;
}

export default function SmartManager({ 
  selectedCount, selectedPaths, onClearSelection, onRefresh, batchAction 
}: SmartManagerProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<AISuggestion[]>([]);
  const [history, setHistory] = useState<OrganizeSnapshot[]>([]);
  const [activeTab, setActiveTab] = useState<"ai" | "manual" | "history">("ai");
  const [moveTarget, setMoveTarget] = useState("");

  const loadHistory = async () => {
    try { const data = await api.getAIHistory(); setHistory(data); } catch {}
  };

  const fetchSuggestions = async () => {
    setLoading(true);
    try { const data = await api.getAISuggestions(); setSuggestions(data); } catch { alert("获取建议失败"); }
    setLoading(false);
  };

  const executeAI = async () => {
    if (!confirm(`确定执行这 ${suggestions.length} 项 AI 整理建议吗？`)) return;
    setLoading(true);
    try {
      const res = await api.executeAISuggestions(suggestions);
      alert(`整理完成！成功: ${res.success.length}`);
      setSuggestions([]);
      loadHistory();
      onRefresh();
    } catch { alert("执行失败"); }
    setLoading(false);
  };

  const rollback = async (id: number) => {
    if (!confirm("确定要回滚吗？")) return;
    setLoading(true);
    try {
      await api.rollbackAI(id);
      alert("回滚执行完毕");
      loadHistory();
      onRefresh();
    } catch { alert("回滚失败"); }
    setLoading(false);
  };

  useEffect(() => { if (open) loadHistory(); }, [open]);

  // 如果有选中项，打开中枢时默认切到“手动”标签
  useEffect(() => { if (selectedCount > 0 && open) setActiveTab("manual"); }, [open, selectedCount]);

  return (
    <>
      {/* 悬浮入口 — 带计数标记 */}
      <div className="fixed bottom-8 right-8 flex flex-col items-end gap-3 z-40">
        {selectedCount > 0 && (
          <div className="bg-blue-600 text-white px-4 py-2 rounded-2xl shadow-2xl animate-bounce text-[10px] font-black uppercase tracking-widest flex items-center gap-2">
            <span className="w-2 h-2 bg-white rounded-full animate-pulse"></span>
            {selectedCount} Selected
          </div>
        )}
        <button 
          onClick={() => setOpen(true)}
          className={`w-14 h-14 rounded-full shadow-2xl flex items-center justify-center hover:scale-110 active:scale-95 transition-all group ${selectedCount > 0 ? "bg-blue-600" : suggestions.length > 0 ? "bg-amber-500" : "bg-slate-800 border border-slate-700"}`}
        >
          <span className="text-2xl group-hover:rotate-12 transition-transform">{selectedCount > 0 ? "📦" : "🤖"}</span>
          {suggestions.length > 0 && <div className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full border-2 border-slate-950 animate-pulse"></div>}
        </button>
      </div>

      {/* 侧面管理抽屉 */}
      {open && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={() => setOpen(false)}></div>
          <div className="relative w-full max-w-lg bg-slate-950 h-full shadow-2xl border-l border-white/5 flex flex-col animate-in slide-in-from-right duration-300">
            {/* Header */}
            <div className="p-8 border-b border-white/5 flex justify-between items-center">
               <div>
                 <h2 className="text-xl font-black text-white flex items-center gap-2 uppercase tracking-tighter">智能管家 <span className="text-[10px] bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full font-black">V3 Pro</span></h2>
                 <p className="text-[10px] text-slate-500 font-bold mt-1 uppercase tracking-widest">Global Selection Management</p>
               </div>
               <button onClick={() => setOpen(false)} className="w-10 h-10 rounded-full border border-slate-800 flex items-center justify-center text-slate-500 hover:text-white">&times;</button>
            </div>

            {/* Tabs */}
            <div className="flex px-8 pt-4 gap-6 bg-slate-950">
              <button onClick={() => setActiveTab("ai")} className={`pb-3 text-xs font-black uppercase tracking-widest transition-all border-b-2 ${activeTab === "ai" ? "border-blue-500 text-blue-400" : "border-transparent text-slate-600 hover:text-slate-400"}`}>AI 建议</button>
              <button onClick={() => setActiveTab("manual")} className={`pb-3 text-xs font-black uppercase tracking-widest transition-all border-b-2 ${activeTab === "manual" ? "border-blue-500 text-blue-400" : "border-transparent text-slate-600 hover:text-slate-400"}`}>批量操作 ({selectedCount})</button>
              <button onClick={() => setActiveTab("history")} className={`pb-3 text-xs font-black uppercase tracking-widest transition-all border-b-2 ${activeTab === "history" ? "border-purple-500 text-purple-400" : "border-transparent text-slate-600 hover:text-slate-400"}`}>历史</button>
            </div>

            <div className="flex-1 overflow-y-auto p-8 no-scrollbar bg-slate-950">
              {activeTab === "ai" && (
                <div className="space-y-6">
                  {suggestions.length === 0 ? (
                    <div className="text-center py-20 bg-slate-900/40 rounded-3xl border border-dashed border-slate-800">
                       <button onClick={fetchSuggestions} disabled={loading} className="bg-blue-600 hover:bg-blue-500 px-10 py-3 rounded-2xl font-black text-xs uppercase tracking-widest transition-all shadow-xl shadow-blue-900/20">
                         {loading ? "AI Analyzing..." : "Run AI Scan"}
                       </button>
                    </div>
                  ) : (
                    <>
                      {suggestions.map((s, i) => (
                        <div key={i} className="bg-slate-900/60 border border-slate-800/40 p-5 rounded-3xl hover:border-blue-500/30 transition-all group/s">
                           <p className="text-[10px] font-black text-slate-500 line-through truncate">{s.original_path.split(/[\\/]/).pop()}</p>
                           <p className="text-sm font-black text-blue-400 mt-1 uppercase tracking-tight">{s.suggested_rel_path}</p>
                        </div>
                      ))}
                      <button onClick={executeAI} disabled={loading} className="w-full bg-blue-600 hover:bg-blue-500 py-5 rounded-3xl font-black text-sm transition-all shadow-2xl shadow-blue-900/40 uppercase mt-8">Confirm AI Plan</button>
                    </>
                  )}
                </div>
              )}

              {activeTab === "manual" && (
                <div className="space-y-8">
                  {selectedCount > 0 ? (
                    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-5 duration-300">
                      
                      <div className="bg-slate-900/40 border border-slate-800 p-6 rounded-3xl">
                         <div className="flex justify-between items-center mb-4">
                            <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-widest">选中列表清单</h4>
                            <button onClick={onClearSelection} className="text-[10px] font-black text-red-500 uppercase hover:underline">一键清空选区</button>
                         </div>
                         <div className="max-h-60 overflow-y-auto pr-2 custom-scrollbar space-y-2">
                            {selectedPaths.map((p, i) => (
                              <div key={i} className="bg-black/20 p-2.5 rounded-xl border border-white/5 flex justify-between gap-2 items-center">
                                 <span className="text-[10px] font-bold text-slate-400 truncate flex-1">{p.split(/[\\/]/).pop()}</span>
                                 <span className="text-[8px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-500 font-mono">ID: {i+1}</span>
                              </div>
                            ))}
                         </div>
                      </div>

                      <div className="grid grid-cols-1 gap-2">
                         <label className="text-[10px] font-black text-slate-500 uppercase ml-2">移动目标目录</label>
                         <input 
                           value={moveTarget} onChange={e => setMoveTarget(e.target.value)}
                           className="bg-slate-900 border border-slate-800 rounded-2xl px-5 py-3 text-sm focus:border-blue-500 outline-none transition-all"
                           placeholder="输入物理路径..."
                         />
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4">
                        <button onClick={() => batchAction("move", moveTarget)} className="bg-blue-600 font-black py-4 rounded-3xl text-xs uppercase tracking-widest shadow-xl shadow-blue-900/20">批量移动</button>
                        <button onClick={() => batchAction("delete")} className="bg-red-600 font-black py-4 rounded-3xl text-xs uppercase tracking-widest shadow-xl shadow-red-900/20 hover:bg-red-500 transition-all">批量删除</button>
                      </div>

                      <button 
                        onClick={() => { onClearSelection(); setOpen(false); }}
                        className="w-full text-slate-500 font-bold text-[10px] uppercase hover:text-white mt-4 border border-slate-900 py-3 rounded-2xl hover:bg-slate-900/50 transition-all"
                      >
                         取消并退出
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center h-80 opacity-20">
                       <span className="text-6xl mb-6 grayscale">🖱️</span>
                       <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest text-center leading-loose">
                         当前暂无选中的项目<br/>请先在媒体库中勾选影片
                       </p>
                    </div>
                  )}
                </div>
              )}

              {activeTab === "history" && (
                <div className="space-y-4">
                  {history.map((h, i) => (
                    <div key={i} className="bg-slate-900/60 border border-slate-800/40 p-6 rounded-3xl flex justify-between items-center group">
                       <div>
                          <p className="text-xs font-black text-slate-300 uppercase">Snapshot #{h.id}</p>
                          <p className="text-[9px] text-slate-500 font-bold mt-1.5 uppercase">{h.time} // {h.ops.length} Items</p>
                       </div>
                       <button onClick={() => rollback(h.id)} className="bg-red-500/10 text-red-500 border border-red-500/20 px-4 py-2 rounded-xl text-[9px] font-black uppercase hover:bg-red-500 hover:text-white transition-all">Rollback</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
