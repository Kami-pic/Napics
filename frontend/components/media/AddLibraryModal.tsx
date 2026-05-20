// 分类添加媒体文件夹弹窗
"use client";
import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import { CATEGORY_TAG_LABELS } from "@/lib/folderTypes";
import PathInput from "@/components/settings/PathInput";

interface AddLibraryModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (paths: string[], libraryName: string) => void;
}

const TAG_OPTIONS = Object.entries(CATEGORY_TAG_LABELS) as [string, string][];

export default function AddLibraryModal({ open, onClose, onSuccess }: AddLibraryModalProps) {
  const [paths, setPaths] = useState<string[]>([""]);
  const [name, setName] = useState("");
  const [categoryTag, setCategoryTag] = useState("movie");
  const [excludeDirs, setExcludeDirs] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const reset = useCallback(() => {
    setPaths([""]); setName(""); setCategoryTag("movie");
    setExcludeDirs(""); setError("");
  }, []);

  const handleClose = useCallback(() => { reset(); onClose(); }, [reset, onClose]);  const handleSubmit = useCallback(async () => {
    const cleanPaths = paths.map(p => p.trim()).filter(Boolean);
    if (!cleanPaths.length) { setError("请至少添加一个路径"); return; }
    setSubmitting(true); setError("");
    try {
      const libName = name.trim() || cleanPaths[0].replace(/[\\/]+$/, "").split(/[\\/]/).pop() || "媒体库";
      const excludeList = excludeDirs.split(/[,\n]/).map(s => s.trim()).filter(Boolean);
      // 同时写入 scan_paths（新路径放最前面）和 media_libraries
      const config = await api.getConfig();
      const existingPaths = (config.scan_paths || []).filter((p: string) => p.trim());
      const newScanPaths = [...cleanPaths.filter(p => !existingPaths.includes(p)), ...existingPaths];
      await api.saveConfig({ ...config, scan_paths: newScanPaths });
      // 记录分类信息
      const res = await api.addLibrary({
        name: libName,
        category_tag: categoryTag,
        paths: cleanPaths,
        exclude_dirs: excludeList,
      });
      handleClose();
      onSuccess(cleanPaths, res.name || libName);
    } catch (e: any) { setError(e.message || "请求失败"); }
    finally { setSubmitting(false); }
  }, [paths, name, categoryTag, excludeDirs, handleClose, onSuccess]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-8 z-50"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}>
      <div className="bg-[var(--background)] border border-white/[0.06] rounded-2xl w-full max-w-lg p-6">
        <h2 className="text-base font-bold text-white mb-5">添加分类文件夹</h2>

        {/* 标签选择（放大强调） */}
        <div className="mb-5">
          <label className="text-sm text-slate-300 mb-2 block font-medium">类型</label>
          <div className="grid grid-cols-3 gap-2">
            {TAG_OPTIONS.map(([value, label]) => (
              <button key={value} onClick={() => setCategoryTag(value)}
                className={`py-2.5 rounded-xl text-sm font-medium transition-all ${
                  categoryTag === value
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
                    : "bg-white/[0.04] text-slate-500 border border-white/[0.06] hover:text-slate-300 hover:bg-white/[0.06]"
                }`}>{label}</button>
            ))}
          </div>
        </div>

        {/* 路径 */}
        <div className="mb-4">
          <label className="text-sm text-slate-300 mb-2 block font-medium">路径</label>
          {paths.map((p, i) => (
            <div key={i} className="mb-2">
              <PathInput
                value={p}
                onChange={v => {
                  const n = [...paths]; n[i] = v; setPaths(n);
                  // 自动填充名称（取最后一段目录名）
                  if (!name && v) {
                    const folderName = v.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || "";
                    setName(folderName);
                  }
                }}
                onDelete={paths.length > 1 ? () => setPaths(paths.filter((_, j) => j !== i)) : undefined}
                placeholder="如 Z:\Movies 或 \\NAS\media 或 /volume1/video"
              />
            </div>
          ))}
          <button onClick={() => setPaths([...paths, ""])} className="text-xs text-blue-400 hover:text-blue-300">+ 添加路径</button>
        </div>

        {/* 名称 */}
        <div className="mb-4">
          <label className="text-sm text-slate-300 mb-2 block font-medium">文件夹名称</label>
          <input value={name} onChange={e => setName(e.target.value)}
            placeholder={paths[0]?.trim().replace(/[\\/]+$/, "").split(/[\\/]/).pop() || "选择路径后自动填充"}
            className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-blue-500/30 placeholder:text-slate-600" />
        </div>

        {/* 排除 */}
        <div className="mb-4">
          <label className="text-sm text-slate-300 mb-2 block font-medium">排除目录<span className="text-slate-600 font-normal ml-1">可选</span></label>
          <input value={excludeDirs} onChange={e => setExcludeDirs(e.target.value)}
            placeholder="用逗号分隔，如 样片,花絮"
            className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-blue-500/30 placeholder:text-slate-600" />
        </div>

        {error && <p className="text-xs text-red-400 mb-3">{error}</p>}

        <div className="flex gap-3 mt-5">
          <button onClick={handleSubmit} disabled={submitting}
            className="flex-1 bg-blue-600 hover:bg-blue-500 py-2.5 rounded-xl text-sm font-medium transition-all disabled:opacity-50">
            {submitting ? "添加中..." : "添加"}
          </button>
          <button onClick={handleClose} className="flex-1 bg-white/[0.06] hover:bg-white/[0.08] py-2.5 rounded-xl text-sm text-slate-400 transition-all">取消</button>
        </div>
      </div>
    </div>
  );
}
