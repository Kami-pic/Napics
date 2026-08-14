// 路径输入组件：文件夹选择按钮 + 输入框 + 可选类型标签下拉 + 可选删除按钮
"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import FolderPicker from "./FolderPicker";

export interface PathInputProps {
  value: string;
  onChange: (value: string) => void;
  /** 多选回调：选择多个文件夹时触发 */
  onMultiSelect?: (paths: string[]) => void;
  /** 类型标签下拉（传入则显示） */
  tag?: string;
  onTagChange?: (tag: string) => void;
  /** 删除按钮（传入则显示） */
  onDelete?: () => void;
  /** placeholder 文本 */
  placeholder?: string;
}

const TAG_OPTIONS: [string, string][] = [
  ["movie", "电影"],
  ["tv", "电视剧"],
  ["anime_tv", "动画番剧"],
  ["anime_movie", "动画电影"],
  ["variety", "综艺"],
  ["other", "其他"],
];

export default function PathInput({ value, onChange, onMultiSelect, tag, onTagChange, onDelete, placeholder = "选择或输入路径" }: PathInputProps) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [reachable, setReachable] = useState<boolean | null>(null);
  const [hint, setHint] = useState("");

  // 校验路径在后端是否真的能访问到。
  // Docker 部署最容易踩的坑：填了宿主机路径，但容器里没挂载该路径，
  // 结果扫描永远没有结果又不报错。这里提前给出提示。
  useEffect(() => {
    const path = value.trim();
    if (!path) {
      setReachable(null);
      setHint("");
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const res = await api.checkPath(path);
        if (cancelled) return;
        const ok = res.exists && res.is_dir && res.readable;
        setReachable(ok);
        setHint(ok ? "" : res.hint);
      } catch {
        if (!cancelled) {
          setReachable(null);
          setHint("");
        }
      }
    }, 600);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [value]);

  const handleSelect = useCallback((path: string) => {
    onChange(path);
  }, [onChange]);

  return (
    <div className="space-y-1">
      <div className="group flex gap-1.5 items-center">
        <button onClick={() => setPickerOpen(true)} title="浏览文件夹"
          className="w-8 h-[36px] flex items-center justify-center rounded-lg bg-white/[0.04] border border-white/[0.06] hover:bg-white/[0.08] transition-all flex-shrink-0">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-slate-400">
            <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
        </button>
        <div className={`flex-1 flex items-center bg-white/[0.04] border rounded-lg overflow-hidden focus-within:border-blue-500/30 ${
          reachable === false ? "border-amber-500/40" : "border-white/[0.06]"
        }`}>
          {tag !== undefined && onTagChange && (
            <select value={tag} onChange={e => onTagChange(e.target.value)}
              className="bg-transparent text-[10px] font-medium px-2 py-2 text-blue-400 outline-none cursor-pointer border-r border-white/[0.06] flex-shrink-0">
              {TAG_OPTIONS.map(([v, label]) => (
                <option key={v} value={v}>{label}</option>
              ))}
            </select>
          )}
          <input value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
            className="flex-1 bg-transparent px-2.5 py-2 text-sm font-mono text-slate-300 outline-none placeholder:text-slate-600" />
          {reachable === true && (
            <span title="服务端可访问" className="flex-shrink-0 mr-1.5 text-emerald-400/70">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </span>
          )}
          {onDelete && (
            <button onClick={onDelete} aria-label="删除该路径"
              className="w-7 h-7 flex items-center justify-center text-red-400/0 group-hover:text-red-400/60 hover:!text-red-400 transition-all flex-shrink-0 mr-0.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
            </button>
          )}
        </div>
      </div>

      {reachable === false && hint && (
        <div className="ml-[38px] px-2.5 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 leading-relaxed">
          {hint}
        </div>
      )}

      <FolderPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={handleSelect}
        onMultiSelect={onMultiSelect}
        initialPath={value.trim()}
      />
    </div>
  );
}
