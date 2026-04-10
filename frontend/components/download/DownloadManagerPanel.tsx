// 下载管理面板：任务列表 + 进度监控 + 整理替换详情 + 归档
"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import type { DownloadTask } from "@/types";
import { api } from "@/lib/api";
import { FileTree } from "./FileTreeNode";

type StatusFilter = "" | "downloading" | "completed" | "awaiting_confirm" | "failed";

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: "等待中", color: "text-slate-400" },
  downloading: { label: "下载中", color: "text-blue-400" },
  cloud_done: { label: "云端完成", color: "text-cyan-400" },
  completed: { label: "已完成", color: "text-green-400" },
  relocating: { label: "归位中", color: "text-purple-400" },
  awaiting_confirm: { label: "待整理", color: "text-yellow-400" },
  archived: { label: "已归档", color: "text-slate-500" },
  failed: { label: "失败", color: "text-red-400" },
  lost: { label: "丢失", color: "text-red-500" },
  unknown: { label: "未知", color: "text-slate-600" },
  cancelled: { label: "已取消", color: "text-slate-500" },
};

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function DownloadManagerPanel({ open, onClose }: Props) {
  const [tasks, setTasks] = useState<DownloadTask[]>([]);
  const [filter, setFilter] = useState<StatusFilter>("");
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // 视图控制：list 为列表，wash 为整理替换详情
  const [view, setView] = useState<"list" | "wash">("list");
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [dryRunData, setDryRunData] = useState<{taskId: string, targetName: string, pairs: any[], plan: any, newFilesAll: any[], oldTree?: any[], newTree?: any[], planTree?: any[]} | null>(null);
  
  // 推演结果缓存：taskId -> dryRunData
  const [washCache, setWashCache] = useState<Record<string, any>>({});
  
  const pollRef = useRef<ReturnType<typeof setInterval>>(undefined);

  const loadTasks = useCallback(async () => {
    try {
      const d = await api.getDownloadTasks(filter || undefined);
      setTasks(d.tasks || []);
    } catch { /* ignore */ }
  }, [filter]);

  const [syncingQb, setSyncingQb] = useState(false);
  const [syncMsg, setSyncMsg] = useState("");

  const handleSyncFromQb = useCallback(async () => {
    setSyncingQb(true);
    setSyncMsg("");
    try {
      const res = await api.syncDownloadProgress();
      await loadTasks();
      const parts = [];
      if (res.imported > 0) parts.push(`导入 ${res.imported} 个新任务`);
      if (res.updated > 0) parts.push(`更新 ${res.updated} 个`);
      setSyncMsg(parts.length > 0 ? parts.join("，") : "已同步，无新增");
    } catch (e) {
      setSyncMsg("同步失败");
    }
    setSyncingQb(false);
    setTimeout(() => setSyncMsg(""), 8000);
  }, [loadTasks]);

  useEffect(() => {
    if (open) {
      setWashCache({});  // 每次打开面板清空缓存，确保使用最新数据
      loadTasks();
      pollRef.current = setInterval(async () => {
        if (view === "wash") return; // 详情页暂停全局轮询
        try {
          const d = await api.getDownloadProgress();
          const progressMap = new Map<string, any>((d.tasks || []).map((t: any) => [t.id, t]));
          setTasks(prev => prev.map(t => {
            const updated = progressMap.get(t.id);
            if (updated) return { ...t, ...updated };
            return t;
          }));
        } catch { /* ignore */ }
      }, 4000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [open, loadTasks, view]);

  // 进入“整理替换”二级页面
  const handleEnterWash = async (taskId: string, mediaName: string) => {
    setActiveTaskId(taskId);
    if (washCache[taskId]) {
      setDryRunData(washCache[taskId]);
      setView("wash");
      return;
    }

    setConfirmingId(taskId);
    try {
      const data = await api.organizeDryRun(taskId, false);
      if (data.status === "awaiting_confirm") {
         const result = { 
           taskId, targetName: mediaName, 
           pairs: data.coexist_pairs || [], 
           plan: data.plan,
           newFilesAll: data.new_files_all || [],
           oldTree: data.old_tree || [],
           newTree: data.new_tree || [],
           planTree: data.plan_tree || [],
         };
         setDryRunData(result);
         setWashCache(prev => ({ ...prev, [taskId]: result }));
         setView("wash");
      } else {
         alert(`${data.message || '未发现需要整理替换的旧资源'}（状态: ${data.status}）`);
         loadTasks();
      }


    } catch(e: any) {
      const msg = e.name === "AbortError" ? "请求超时，可能是保存路径过大或 NAS 不可达" : e.message;
      alert("探测失败: " + msg);
    } finally {
      setConfirmingId(null);
    }
  };

  const handleBackToList = () => {
    setView("list");
    setDryRunData(null);
    setActiveTaskId(null);
  };

  const handleExecuteAction = async (mode: "purge" | "archive_both" | "full_wash") => {
    if (!dryRunData) return;
    const { taskId, plan } = dryRunData;
    
    setConfirmingId(taskId);
    try {
      let res;
      if (mode === "purge") {
        if (!confirm("确定只清理旧资源吗？这会永久删除库中的存量文件。")) return;
        res = await api.purgeOldData(taskId);
      } else if (mode === "archive_both") {
        res = await api.archiveBoth(taskId, plan);
      } else {
        res = await api.organizeExecute(taskId, plan);
      }

      if (res.status === "archived" || res.status === "ok") {
        alert(res.message || "操作已成功执行");
        // 清理缓存并返回
        setWashCache(prev => {
          const next = { ...prev };
          delete next[taskId];
          return next;
        });
        handleBackToList();
        loadTasks();
      } else {
        alert("执行失败: " + (res.message || res.error));
      }
    } catch (e: any) {
      alert("接口调用失败: " + e.message);
    } finally {
      setConfirmingId(null);
    }
  };

  const handleDelete = async (taskId: string) => {
    if (!confirm("确定删除这条下载记录？（不影响磁盘文件）")) return;
    setDeletingId(taskId);
    try { await api.deleteDownloadTask(taskId); loadTasks(); } catch { alert("删除失败"); }
    setDeletingId(null);
  };

  const handleClearCompleted = async () => {
    const completedIds = tasks.filter(t => ["completed", "archived", "cancelled", "failed", "lost", "unknown"].includes(t.status)).map(t => t.id);
    if (completedIds.length === 0) return;
    if (!confirm(`确定清除 ${completedIds.length} 条已处理的记录？`)) return;
    try { await api.deleteDownloadTasks(completedIds); loadTasks(); } catch { alert("清除失败"); }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-6 z-50">
      <div className="bg-[#141414] border border-white/[0.06] rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col relative overflow-hidden shadow-2xl">
        
        {/* 视图切换容器：必须是 flex-row 且 h-full 确保子页面撑满 */}
        <div className={`flex-1 flex flex-row transition-transform duration-300 ease-in-out ${view === 'wash' ? '-translate-x-1/2' : 'translate-x-0'}`} 
             style={{ width: '200%', height: '100%' }}>
          
          {/* 1. 列表页 (List View) */}
          <div className="w-1/2 flex flex-col h-full border-r border-white/[0.04] min-w-0">
            <div className="p-5 border-b border-white/[0.06] flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <h2 className="text-[15px] font-bold text-white">下载管理</h2>
                <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.06] text-slate-400">{tasks.length} 个任务</span>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={handleSyncFromQb} disabled={syncingQb}
                  className="px-3 py-1.5 rounded-lg text-[11px] bg-white/[0.04] text-slate-500 hover:text-blue-400 hover:bg-blue-500/10 transition-colors">
                  {syncingQb ? "同步中..." : "从 qB 同步"}
                </button>
                {syncMsg && <span className="text-[10px] text-green-400">{syncMsg}</span>}
                <button onClick={handleClearCompleted}
                  className="px-3 py-1.5 rounded-lg text-[11px] bg-white/[0.04] text-slate-500 hover:text-slate-300">
                  清除已完成
                </button>
                <button onClick={onClose} className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:text-white">✕</button>
              </div>
            </div>

            <div className="px-5 py-3 flex gap-2 border-b border-white/[0.04] shrink-0">
              {(["", "downloading", "completed", "awaiting_confirm", "failed"] as StatusFilter[]).map(s => (
                <button key={s} onClick={() => setFilter(s)}
                  className={`px-3 py-1 rounded-lg text-[11px] transition-colors ${filter === s ? "bg-blue-600 text-white" : "bg-white/[0.04] text-slate-500 hover:text-slate-300"}`}>
                  {s === "" ? "全部" : (s === "downloading" ? "活跃中" : STATUS_LABELS[s]?.label || s)}
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-3 min-h-0 custom-scrollbar">
              {tasks.length === 0 && (
                <div className="h-40 flex flex-col items-center justify-center opacity-20">
                  <p className="text-[11px]">暂无记录</p>
                </div>
              )}
              {tasks.map(task => {
                const st = STATUS_LABELS[task.status] || { label: task.status, color: "text-slate-500" };
                const isDone = ["completed", "awaiting_confirm"].includes(task.status);
                const isSyncing = confirmingId === task.id;

                return (
                  <div key={task.id} className="bg-[#1a1a1a] rounded-xl border border-white/[0.04] p-4 hover:border-white/[0.1] transition-all">
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 pr-4">
                        <p className="text-sm text-white font-medium truncate mb-1">{task.media_name}</p>
                        <div className="flex items-center gap-3">
                          <span className={`text-[10px] font-medium ${st.color}`}>{st.label}</span>
                          <span className="text-[10px] text-slate-600 truncate">{task.save_path}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {isDone && (
                          <button onClick={() => handleEnterWash(task.id, task.media_name)} disabled={isSyncing}
                            className="px-4 py-1.5 rounded-lg text-[11px] bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 border border-blue-500/20 transition-all flex items-center gap-2">
                            {isSyncing ? <div className="w-3 h-3 border-2 border-blue-400/20 border-t-blue-400 rounded-full animate-spin" /> : null}
                            整理替换
                          </button>
                        )}
                        <button onClick={() => handleDelete(task.id)} className="w-8 h-8 flex items-center justify-center text-slate-600 hover:text-red-400">✕</button>
                      </div>
                    </div>
                    {/* 只要任务活跃或有进度，就显示进度条 */}
                    {(["downloading", "unknown", "lost"].includes(task.status) || (task.status === "completed" && task.progress < 1)) && (
                      <div className="mt-3">
                        <div className="w-full bg-white/[0.06] rounded-full h-1 overflow-hidden sm:h-1.5">
                          <div className="bg-blue-500 h-full transition-all" style={{ width: `${task.progress * 100}%` }} />
                        </div>
                        <div className="flex justify-between mt-1 text-[9px] text-slate-500 font-mono">
                          <span>{(task.progress * 100).toFixed(1)}%</span>
                          <span>{task.speed || "等待中"} / {task.eta || "--:--"}</span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* 2. 详情页 (Wash View) */}
          <div className="w-1/2 flex flex-col h-full bg-[#0d0d0d] min-w-0">
            {dryRunData ? (
              <>
                <div className="p-5 border-b border-white/[0.06] flex items-center gap-4 shrink-0">
                  <button onClick={handleBackToList} className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-slate-400 hover:text-white transition-colors">←</button>
                  <div className="min-w-0">
                    <h2 className="text-[14px] font-bold text-white truncate">整理替换预览：{dryRunData.targetName}</h2>
                    <p className="text-[10px] text-slate-500">发现存量冲突，请选择应用方案</p>
                  </div>
                </div>

                <div className="flex-1 overflow-hidden p-5 min-h-0">
                  <div className="grid grid-cols-3 gap-5 h-full min-h-0">
                    
                    {/* 第一栏：旧资源 */}
                    <div className="flex flex-col bg-[#1a1a1a] border border-red-500/10 rounded-2xl p-4 min-h-0">
                      <p className="text-[11px] font-bold text-red-400 mb-2 flex items-center justify-between shrink-0">
                        旧资源 (库中存量)
                        <span className="text-[9px] font-normal text-red-400/40">{dryRunData.pairs.filter((p: any) => p.category !== "non_video").length} 个待清理</span>
                      </p>
                      <p className="text-[9px] text-slate-600 mb-3 shrink-0">🗑 待清理 · ⚠️ 保留不动 · 📁 含视频文件夹</p>
                      <div className="flex-1 overflow-y-auto pr-1 custom-scrollbar">
                        <FileTree tree={dryRunData.oldTree || []} variant="old" />
                      </div>
                      <div className="mt-4 shrink-0">
                        <button onClick={() => handleExecuteAction("purge")} disabled={!!confirmingId}
                          className="w-full py-2.5 rounded-xl text-[11px] font-bold bg-white/[0.04] text-red-400 hover:bg-red-500/10 border border-red-500/10 transition-all">
                          只清理旧数据
                        </button>
                        <p className="text-[8px] text-slate-600 mt-1.5 text-center">旧文件移入回收站（可恢复），新下载不动</p>
                      </div>
                    </div>

                    {/* 第二栏：新资源（完整文件列表） */}
                    <div className="flex flex-col bg-[#1a1a1a] border border-white/[0.06] rounded-2xl p-4 min-h-0">
                      <p className="text-[11px] font-bold text-slate-400 mb-2 flex items-center justify-between shrink-0">
                        新资源 (原始文件)
                        <span className="text-[9px] font-normal text-slate-600">{(dryRunData.newFilesAll || []).length} 个文件</span>
                      </p>
                      <p className="text-[9px] text-slate-600 mb-3 shrink-0">当前下载的完整文件列表</p>
                      <div className="flex-1 overflow-y-auto pr-1 custom-scrollbar">
                        <FileTree tree={dryRunData.newTree || []} variant="new" />
                      </div>
                      <div className="mt-4 shrink-0">
                        <button onClick={() => handleExecuteAction("archive_both")} disabled={!!confirmingId}
                          className="w-full py-2.5 rounded-xl text-[11px] font-bold bg-white/[0.04] text-slate-300 hover:bg-white/[0.08] border border-white/[0.08] transition-all">
                          保留新旧并归档
                        </button>
                        <p className="text-[8px] text-slate-600 mt-1.5 text-center">旧文件移至 [旧资源备份] 子目录，新旧共存</p>
                      </div>
                    </div>


                    {/* 第三栏：标准化结果预览 */}
                    <div className="flex flex-col bg-[#1a1a1a] border border-blue-500/20 rounded-2xl p-4 shadow-[0_0_30px_rgba(59,130,246,0.05)] min-h-0">
                      <p className="text-[11px] font-bold text-blue-400 mb-2 shrink-0">标准化结果 (预览)</p>
                      <p className="text-[9px] text-slate-600 mb-3 shrink-0">✅ 重命名 · ⏭ 跳过 · 📁 新建目录</p>
                      <div className="flex-1 overflow-y-auto pr-1 custom-scrollbar">
                        <FileTree tree={dryRunData.planTree || []} variant="plan" />
                      </div>
                      <div className="mt-4 shrink-0">
                        <button onClick={() => handleExecuteAction("full_wash")} disabled={!!confirmingId}
                          className="w-full py-2.5 rounded-xl text-[11px] font-bold bg-blue-600 text-white hover:bg-blue-500 shadow-lg shadow-blue-600/30 transition-all flex items-center justify-center gap-2 active:scale-[0.98]">
                          {confirmingId === dryRunData.taskId ? <div className="w-3 h-3 border-2 border-white/20 border-t-white rounded-full animate-spin" /> : null}
                          一键整理并刮削
                        </button>
                        <p className="text-[8px] text-slate-600 mt-1.5 text-center">旧文件→回收站，新文件→标准化改名 + NFO + 海报</p>
                      </div>
                    </div>


                  </div>
                </div>
              </>
            ) : (
                <div className="flex-1 flex items-center justify-center text-slate-600 text-[11px]">加载中...</div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
