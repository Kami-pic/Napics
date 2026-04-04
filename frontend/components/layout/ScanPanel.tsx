// 扫描控制面板 — 路径输入 + 进度条 + 停止按钮
"use client";
import type { ScanProgress } from "@/types";

interface ScanPanelProps {
  paths: string[];
  setPaths: (p: string[]) => void;
  scanning: boolean;
  scanProgress: ScanProgress;
  onScan: () => void;
  onStop: () => void;
}

export default function ScanPanel({ paths, setPaths, scanning, scanProgress, onScan, onStop }: ScanPanelProps) {
  return (
    <section className="bg-slate-900 border border-slate-800 p-5 rounded-2xl mb-6">
      <div className="flex flex-col gap-3">
        {paths.map((p, i) => (
          <div key={i} className="flex gap-3">
            <input value={p} onChange={e => { const n = [...paths]; n[i] = e.target.value; setPaths(n); }}
              placeholder="NAS 路径（如 Z:\Movies）" className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm" />
            {paths.length > 1 && <button onClick={() => setPaths(paths.filter((_, j) => j !== i))} className="text-red-400 text-xs px-2 hover:text-red-300">删除</button>}
          </div>
        ))}
        <div className="flex justify-between items-center">
          <button onClick={() => setPaths([...paths, ""])} className="text-xs text-blue-400 hover:text-blue-300">+ 添加目录</button>
          <button onClick={onScan} disabled={scanning} className="bg-blue-600 px-8 py-2 rounded-xl text-sm font-bold hover:bg-blue-500 disabled:opacity-50 transition-all">{scanning ? "扫描中..." : "开始扫描"}</button>
        </div>
      </div>
      {scanning && (
        <div className="mt-4 p-4 bg-slate-950 border border-blue-500/20 rounded-xl">
          <div className="flex justify-between items-center mb-2">
            <span className="text-blue-400 text-sm font-bold flex items-center gap-2">
              <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin"></div>深度分析中...
            </span>
            <div className="flex gap-3 items-center">
              <span className="text-slate-400 text-xs">{scanProgress.current}/{scanProgress.total}</span>
              <button onClick={onStop} className="text-xs bg-red-600/20 text-red-400 px-2 py-0.5 rounded border border-red-500/30">停止</button>
            </div>
          </div>
          <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden">
            <div className="bg-blue-600 h-full transition-all duration-300" style={{ width: `${scanProgress.total > 0 ? (scanProgress.current / scanProgress.total * 100) : 0}%` }}></div>
          </div>
          <p className="text-[10px] text-slate-600 mt-1 truncate">{scanProgress.lastFile || "准备中..."}</p>
        </div>
      )}
    </section>
  );
}
