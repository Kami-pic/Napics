// 工具栏（和面包屑同行右侧）：撤回操作 | 快速同步、批处理、视图切换
"use client";
import type { ViewMode } from "@/types";
import { api } from "@/lib/api";
import { iterSseEvents } from "@/lib/sse/framer";

interface ToolbarProps {
  viewMode: ViewMode;
  setViewMode: (m: ViewMode) => void;
  batchMode: boolean;
  onToggleBatch: () => void;
  onRefresh: () => void;
  onOpenHistory: () => void;
  onOpenReport: () => void;
  syncing: boolean;
  setSyncing: (v: boolean) => void;
  syncMsg: string;
  setSyncMsg: (v: string) => void;
  syncDone: boolean;
  setSyncDone: (v: boolean) => void;
}

export default function Toolbar({
  viewMode, setViewMode, batchMode, onToggleBatch,
  onRefresh, onOpenHistory, onOpenReport,
  syncing, setSyncing, syncMsg, setSyncMsg, syncDone, setSyncDone,
}: ToolbarProps) {

  const handleSync = async () => {
    setSyncing(true); setSyncMsg("");
    try {
      const response = await api.quickSync();
      if (!response.ok) {
        setSyncMsg("失败");
        setSyncing(false);
        setTimeout(() => setSyncMsg(""), 4000);
        return;
      }
      if (!response.body) { setSyncing(false); return; }
      let lastDone = false;
      for await (const part of iterSseEvents(response.body)) {
        if (!part.startsWith("data: ")) continue;
        // framer 会吐出流末尾未闭合的残留，这里可能是半截 JSON
        try {
          const data = JSON.parse(part.replace("data: ", ""));
          if (data.type === "status") setSyncMsg(data.message);
          else if (data.type === "progress") {
            const fileName = data.file || "";
            const truncName = fileName.length > 30 ? fileName.slice(0, 12) + "..." + fileName.slice(-12) : fileName;
            setSyncMsg(`${data.current}/${data.total}${truncName ? " " + truncName : ""}`);
          }
          else if (data.type === "done") {
            setSyncMsg(`+${data.added} -${data.removed}`);
            lastDone = true;
          }
        } catch {}
      }
      if (lastDone) onRefresh();
      else if (!syncMsg) setSyncMsg("完成");
    } catch (e) {
      console.error("快速同步失败:", e);
      setSyncMsg("失败");
      // 即使流断了也尝试刷新（后端可能已经保存了部分结果）
      onRefresh();
    }
    setSyncing(false);
    setSyncDone(true);
    setTimeout(() => { setSyncMsg(""); setSyncDone(false); }, 5000);
  };

  return (
    <div className="flex items-center gap-1.5 flex-shrink-0">
      <button onClick={handleSync} disabled={syncing}
        className={`px-2.5 py-1.5 text-xs rounded-lg transition-all disabled:opacity-50 ${
          syncDone ? "text-green-400 bg-green-500/10" : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]"
        }`}>
        {syncing ? "同步中..." : syncDone ? "✓ 同步完成" : "快速同步"}
      </button>
      <div className="w-px h-3.5 bg-white/[0.06]" />
      <button onClick={onOpenHistory}
        className="px-2.5 py-1.5 text-xs text-slate-500 hover:text-slate-300 hover:bg-white/[0.04] rounded-lg transition-all">
        撤回操作
      </button>
      <div className="w-px h-3.5 bg-white/[0.06]" />
      <button onClick={onOpenReport}
        className="px-2.5 py-1.5 text-xs text-slate-500 hover:text-slate-300 hover:bg-white/[0.04] rounded-lg transition-all">
        健康报告
      </button>
      <div className="w-px h-3.5 bg-white/[0.06]" />
      <button onClick={onToggleBatch}
        className={`px-2.5 py-1.5 text-xs rounded-lg transition-all ${batchMode ? "text-blue-400 bg-blue-500/10" : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]"}`}>
        {batchMode ? "退出批处理" : "批处理"}
      </button>
      <div className="w-px h-3.5 bg-white/[0.06]" />
      <div className="flex items-center gap-0.5 bg-[#1a1a1a] p-0.5 rounded-lg border border-white/[0.06]">
        <button onClick={() => setViewMode("card")}
          className={`px-2.5 py-1 rounded-md text-xs transition-all ${viewMode === "card" ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"}`}>
          卡片
        </button>
        <button onClick={() => setViewMode("list")}
          className={`px-2.5 py-1 rounded-md text-xs transition-all ${viewMode === "list" ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"}`}>
          列表
        </button>
      </div>
    </div>
  );
}
