// 批量操作面板
"use client";
import { useState } from "react";
import type { VideoInfo } from "@/types";
import { api } from "@/lib/api";

export function BatchPanel({ selectedPaths, batchAction, onClear, onSearch, onRefresh, currentVideos, onSelectAll, onInvertSelect }: { selectedPaths: Set<string>; batchAction: (a: "delete" | "move" | "remove", t?: string) => void; onClear: () => void; onSearch: (q: string) => void; onRefresh: () => void; currentVideos?: VideoInfo[]; onSelectAll?: () => void; onInvertSelect?: () => void }) {
  const [moveTarget, setMoveTarget] = useState("");
  const [copyTarget, setCopyTarget] = useState("");
  const [confirmDel, setConfirmDel] = useState(false);
  const [batchLoading, setBatchLoading] = useState("");
  const paths = Array.from(selectedPaths);

  const handleBatchScrape = async () => {
    setBatchLoading("刮削中...");
    try {
      for (let i = 0; i < paths.length; i++) {
        setBatchLoading(`刮削 (${i + 1}/${paths.length})`);
        try { await api.executeScrape(paths[i]); } catch {}
      }
      onRefresh();
    } catch {}
    setBatchLoading("");
  };

  const handleBatchRename = async (shadowOnly: boolean = true) => {
    const label = shadowOnly ? "生成标准名" : "覆盖文件名";
    if (!shadowOnly && !confirm("确定要将标准名覆盖为真实文件名吗？")) return;
    setBatchLoading(`${label}中...`);
    try {
      const folders = new Set<string>();
      for (const fp of paths) {
        const sep = fp.lastIndexOf("\\") !== -1 ? "\\" : "/";
        folders.add(fp.substring(0, fp.lastIndexOf(sep)));
      }
      for (const folder of folders) {
        await api.renameVideos(folder, false, shadowOnly);
      }
      onRefresh();
    } catch {}
    setBatchLoading("");
  };

  return (
    <div className="flex-1 overflow-y-auto p-5 space-y-5">
      <div className="space-y-1 max-h-[200px] overflow-y-auto">{paths.map((p, i) => <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.02] text-xs"><span className="text-slate-500 w-5">{i + 1}</span><span className="text-slate-300 truncate flex-1">{p.split(/[\\/]/).pop()}</span></div>)}</div>
      {batchLoading && (
        <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
          <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
          <span className="text-xs text-blue-400">{batchLoading}</span>
        </div>
      )}
      <div className="space-y-2">
        <div className="flex gap-2"><input value={moveTarget} onChange={e => setMoveTarget(e.target.value)} placeholder="移动目标路径" className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs outline-none text-slate-400" /><button onClick={() => { if (moveTarget) batchAction("move", moveTarget); }} className="px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 text-xs font-medium">移动</button></div>
        <div className="flex gap-2"><input value={copyTarget} onChange={e => setCopyTarget(e.target.value)} placeholder="复制目标路径" className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs outline-none text-slate-400" /><button onClick={async () => { if (copyTarget) { try { await api.batchManage("copy", paths, copyTarget); onRefresh(); } catch { alert("复制失败"); } } }} className="px-4 py-2 rounded-lg bg-cyan-500/20 text-cyan-400 text-xs font-medium">复制</button></div>
        <div className="grid grid-cols-2 gap-2">
          <button onClick={handleBatchScrape} disabled={!!batchLoading} className="py-2 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-xs text-purple-400 disabled:opacity-50">批量刮削</button>
          <button onClick={() => handleBatchRename(true)} disabled={!!batchLoading} className="py-2 rounded-lg bg-green-500/20 hover:bg-green-500/30 text-xs text-green-400 disabled:opacity-50">生成标准名</button>
        </div>
        <button onClick={() => handleBatchRename(false)} disabled={!!batchLoading} className="w-full py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-xs text-amber-400 disabled:opacity-50">标准名覆盖真名</button>
        {!confirmDel ? <button onClick={() => setConfirmDel(true)} className="w-full py-2.5 rounded-lg bg-white/[0.04] hover:bg-red-500/10 text-sm text-red-400">删除</button> : <div className="flex items-center gap-2 bg-red-500/5 border border-red-500/20 rounded-lg p-2.5"><span className="text-xs text-red-400 flex-1">确定删除？</span><button onClick={() => { batchAction("delete"); setConfirmDel(false); }} className="px-3 py-1 rounded bg-red-600 text-white text-xs">删除</button><button onClick={() => setConfirmDel(false)} className="px-2 py-1 text-xs text-slate-500">取消</button></div>}
        <button onClick={() => batchAction("remove")} className="w-full py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.06] text-sm text-slate-500">从媒体库中移除</button>
        <div className="flex gap-2">
          {onSelectAll && <button onClick={onSelectAll} className="flex-1 py-2 text-xs text-slate-500 hover:text-slate-300 bg-white/[0.04] rounded-lg">全选</button>}
          {onInvertSelect && <button onClick={onInvertSelect} className="flex-1 py-2 text-xs text-slate-500 hover:text-slate-300 bg-white/[0.04] rounded-lg">反选</button>}
          <button onClick={onClear} className="flex-1 py-2 text-xs text-slate-500 hover:text-slate-300 bg-white/[0.04] rounded-lg">清空</button>
        </div>
      </div>
    </div>
  );
}
