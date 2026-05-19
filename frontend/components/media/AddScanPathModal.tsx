// 添加媒体库弹窗（扫描路径模式）
"use client";
import { useState, useCallback } from "react";
import { api } from "@/lib/api";

interface AddScanPathModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (paths: string[]) => void;
}

export default function AddScanPathModal({ open, onClose, onSuccess }: AddScanPathModalProps) {
  const [paths, setPaths] = useState<string[]>([""]);
  const [excludeDirs, setExcludeDirs] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const reset = useCallback(() => { setPaths([""]); setExcludeDirs(""); setError(""); }, []);
  const handleClose = useCallback(() => { reset(); onClose(); }, [reset, onClose]);

  const handleBrowse = useCallback(async (index: number) => {
    try {
      const res = await api.browseFolder();
      if (res.path) { const n = [...paths]; n[index] = res.path; setPaths(n); }
    } catch {}
  }, [paths]);

  const handleSubmit = useCallback(async () => {
    const cleanPaths = paths.map(p => p.trim()).filter(Boolean);
    if (!cleanPaths.length) { setError("请至少添加一个路径"); return; }
    setSubmitting(true); setError("");
    try {
      const config = await api.getConfig();
      const existingPaths = (config.scan_paths || []).filter((p: string) => p.trim());
      const newPaths = [...cleanPaths.filter(p => !existingPaths.includes(p)), ...existingPaths];
      const newExclude = excludeDirs.trim()
        ? [config.exclude_dirs, excludeDirs].filter(Boolean).join(",")
        : config.exclude_dirs;
      await api.saveConfig({ ...config, scan_paths: newPaths, exclude_dirs: newExclude });
      handleClose();
      onSuccess(cleanPaths);
    } catch (e: any) { setError(e.message || "保存失败"); }
    finally { setSubmitting(false); }
  }, [paths, excludeDirs, handleClose, onSuccess]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-8 z-50"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}>
      <div className="bg-[var(--background)] border border-white/[0.06] rounded-2xl w-full max-w-lg p-6">
        <h2 className="text-base font-bold text-white mb-5">添加媒体库</h2>
        <p className="text-xs text-slate-500 mb-4">添加路径后系统会自动扫描并识别其中的影视内容</p>

        {/* 路径 */}
        <div className="mb-4">
          <label className="text-sm text-slate-300 mb-2 block font-medium">扫描路径</label>
          {paths.map((p, i) => (
            <div key={i} className="flex gap-2 mb-2">
              <input value={p} onChange={e => { const n = [...paths]; n[i] = e.target.value; setPaths(n); }}
                placeholder="选择或输入文件夹路径"
                className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm font-mono text-slate-300 outline-none focus:border-blue-500/30 placeholder:text-slate-600" />
              <button onClick={() => handleBrowse(i)} title="选择文件夹"
                className="w-9 h-9 flex items-center justify-center rounded-lg bg-white/[0.04] border border-white/[0.06] hover:bg-white/[0.08] transition-all">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-slate-400">
                  <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
              </button>
              {paths.length > 1 && (
                <button onClick={() => setPaths(paths.filter((_, j) => j !== i))} className="text-red-400 hover:text-red-300 text-xs px-1">✕</button>
              )}
            </div>
          ))}
          <button onClick={() => setPaths([...paths, ""])} className="text-xs text-blue-400 hover:text-blue-300">+ 添加路径</button>
        </div>

        {/* 排除 */}
        <div className="mb-4">
          <label className="text-sm text-slate-300 mb-2 block font-medium">排除目录<span className="text-slate-600 font-normal ml-1">可选</span></label>
          <input value={excludeDirs} onChange={e => setExcludeDirs(e.target.value)}
            placeholder="用逗号分隔，如 @eaDir,#recycle"
            className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-blue-500/30 placeholder:text-slate-600" />
        </div>

        {error && <p className="text-xs text-red-400 mb-3">{error}</p>}

        <div className="flex gap-3 mt-5">
          <button onClick={handleSubmit} disabled={submitting}
            className="flex-1 bg-blue-600 hover:bg-blue-500 py-2.5 rounded-xl text-sm font-medium transition-all disabled:opacity-50">
            {submitting ? "保存中..." : "添加并扫描"}
          </button>
          <button onClick={handleClose} disabled={submitting} className="flex-1 bg-white/[0.06] hover:bg-white/[0.08] py-2.5 rounded-xl text-sm text-slate-400 transition-all disabled:opacity-50">取消</button>
        </div>
      </div>
    </div>
  );
}
