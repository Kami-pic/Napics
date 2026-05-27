// 批处理文字按钮 + 视图切换
"use client";
import type { ViewMode } from "@/types";

interface FilterBarProps {
  viewMode: ViewMode;
  setViewMode: (m: ViewMode) => void;
  batchMode: boolean;
  onToggleBatch: () => void;
}

export default function FilterBar({ viewMode, setViewMode, batchMode, onToggleBatch }: FilterBarProps) {
  return (
    <div className="flex items-center gap-3 flex-shrink-0">
      <button onClick={onToggleBatch}
        className={`text-sm transition-all ${batchMode ? "text-blue-400" : "text-slate-500 hover:text-slate-300"}`}>
        {batchMode ? "退出批处理" : "批处理"}
      </button>
      <div className="w-px h-4 bg-white/[0.06]" />
      <div className="flex items-center gap-1 bg-[#1a1a1a] p-1 rounded-lg border border-white/[0.06]">
        <button onClick={() => setViewMode("card")}
          className={`px-3.5 py-1.5 rounded-md text-sm transition-all ${viewMode === "card" ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"}`}>
          卡片
        </button>
        <button onClick={() => setViewMode("list")}
          className={`px-3.5 py-1.5 rounded-md text-sm transition-all ${viewMode === "list" ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"}`}>
          列表
        </button>
      </div>
    </div>
  );
}
