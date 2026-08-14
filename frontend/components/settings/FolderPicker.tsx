// 网页版文件夹选择器：跨平台（Windows / 飞牛 / 群晖 / Docker 通用）
//
// 原来的实现是让后端弹出系统对话框，那只在后端跑在用户桌面上时可行；
// 容器和 NAS 上都弹不出来。改为后端提供目录列举、这里渲染选择界面。
"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

export interface FolderPickerProps {
  open: boolean;
  onClose: () => void;
  /** 确认选择时回调（单选） */
  onSelect: (path: string) => void;
  /** 多选确认回调，传入则启用多选 */
  onMultiSelect?: (paths: string[]) => void;
  /** 打开时的初始目录 */
  initialPath?: string;
}

interface DirItem {
  name: string;
  path: string;
}

export default function FolderPicker({
  open, onClose, onSelect, onMultiSelect, initialPath = "",
}: FolderPickerProps) {
  const multi = !!onMultiSelect;
  const [cwd, setCwd] = useState("");
  const [parent, setParent] = useState("");
  const [dirs, setDirs] = useState<DirItem[]>([]);
  const [isRootList, setIsRootList] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [manual, setManual] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const listRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async (path: string) => {
    setLoading(true);
    setError("");
    try {
      const res = await api.listDirectories(path);
      setCwd(res.path);
      setParent(res.parent);
      setDirs(res.dirs || []);
      setIsRootList(res.is_root_list);
      setError(res.error || "");
      if (res.path) setManual(res.path);
      // 切换目录后回到列表顶部
      if (listRef.current) listRef.current.scrollTop = 0;
    } catch (e) {
      setError(`读取目录失败：${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    setPicked([]);
    load(initialPath || "");
  }, [open, initialPath, load]);

  // ESC 关闭
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const togglePick = (path: string) => {
    setPicked(prev => prev.includes(path) ? prev.filter(p => p !== path) : [...prev, path]);
  };

  const confirm = () => {
    if (multi) {
      const result = picked.length > 0 ? picked : (manual.trim() ? [manual.trim()] : []);
      if (result.length === 0) return;
      if (result.length === 1) onSelect(result[0]);
      else onMultiSelect!(result);
    } else {
      const target = manual.trim() || cwd;
      if (!target) return;
      onSelect(target);
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 p-4"
      onClick={onClose} role="dialog" aria-modal="true" aria-label="选择文件夹">
      <div className="w-full max-w-2xl max-h-[80vh] flex flex-col rounded-xl bg-[#141414] border border-white/[0.08] shadow-2xl"
        onClick={e => e.stopPropagation()}>

        {/* 标题栏 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
          <h3 className="text-sm font-medium text-slate-200">
            选择文件夹{multi && <span className="ml-2 text-[11px] text-slate-500">可勾选多个</span>}
          </h3>
          <button onClick={onClose} aria-label="关闭"
            className="w-7 h-7 flex items-center justify-center rounded text-slate-500 hover:text-slate-200 hover:bg-white/[0.06]">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 当前路径 + 上一级 */}
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/[0.06]">
          <button
            onClick={() => load(parent)}
            disabled={!parent || loading}
            title="上一级"
            className="w-8 h-8 flex items-center justify-center rounded-lg bg-white/[0.04] border border-white/[0.06]
                       hover:bg-white/[0.08] disabled:opacity-30 disabled:cursor-not-allowed flex-shrink-0">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-400">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
          <button
            onClick={() => load("")}
            disabled={loading}
            title="回到根目录"
            className="h-8 px-2.5 flex items-center rounded-lg bg-white/[0.04] border border-white/[0.06]
                       hover:bg-white/[0.08] text-[11px] text-slate-400 flex-shrink-0">
            根目录
          </button>
          <div className="flex-1 px-2.5 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06]
                          text-xs font-mono text-slate-400 truncate">
            {cwd || "（选择一个磁盘或根目录）"}
          </div>
        </div>

        {/* 目录列表 */}
        <div ref={listRef} className="flex-1 overflow-y-auto min-h-[240px] px-2 py-2">
          {loading && (
            <div className="flex items-center justify-center h-32 text-xs text-slate-500">加载中...</div>
          )}

          {!loading && error && (
            <div className="m-2 px-3 py-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300">
              {error}
            </div>
          )}

          {!loading && !error && dirs.length === 0 && (
            <div className="flex items-center justify-center h-32 text-xs text-slate-600">
              该目录下没有子文件夹
            </div>
          )}

          {!loading && dirs.map(d => (
            <div key={d.path}
              className="group flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/[0.04]">
              {multi && !isRootList && (
                <input type="checkbox" checked={picked.includes(d.path)}
                  onChange={() => togglePick(d.path)}
                  aria-label={`选择 ${d.name}`}
                  className="w-3.5 h-3.5 accent-blue-500 flex-shrink-0 cursor-pointer" />
              )}
              <button onClick={() => load(d.path)}
                className="flex-1 flex items-center gap-2 min-w-0 text-left">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="1.5" className="text-blue-400/70 flex-shrink-0">
                  <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                <span className="text-sm text-slate-300 truncate">{d.name}</span>
              </button>
              {!multi && (
                <button onClick={() => { onSelect(d.path); onClose(); }}
                  className="opacity-0 group-hover:opacity-100 px-2 py-0.5 rounded text-[10px]
                             bg-blue-500/15 text-blue-300 hover:bg-blue-500/25 flex-shrink-0 transition-opacity">
                  选这个
                </button>
              )}
            </div>
          ))}
        </div>

        {/* 手动输入 + 确认 */}
        <div className="px-4 py-3 border-t border-white/[0.06] space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-500 flex-shrink-0">路径</span>
            <input value={manual} onChange={e => setManual(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") confirm(); }}
              placeholder="也可以直接粘贴路径"
              aria-label="手动输入路径"
              className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-2.5 py-1.5
                         text-xs font-mono text-slate-300 outline-none focus:border-blue-500/30
                         placeholder:text-slate-600" />
          </div>

          {multi && picked.length > 0 && (
            <div className="text-[11px] text-blue-300">已勾选 {picked.length} 个文件夹</div>
          )}

          <div className="flex justify-end gap-2 pt-0.5">
            <button onClick={onClose}
              className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:bg-white/[0.06]">
              取消
            </button>
            <button onClick={confirm}
              className="px-3.5 py-1.5 rounded-lg text-xs font-medium bg-blue-500/20 text-blue-300
                         border border-blue-500/30 hover:bg-blue-500/30">
              {multi && picked.length > 1 ? `添加这 ${picked.length} 个` : "确定"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
