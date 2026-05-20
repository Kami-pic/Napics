// 路径输入组件：文件夹选择按钮 + 输入框 + 可选类型标签下拉 + 可选删除按钮
"use client";
import { useCallback } from "react";
import { api } from "@/lib/api";

export interface PathInputProps {
  value: string;
  onChange: (value: string) => void;
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

export default function PathInput({ value, onChange, tag, onTagChange, onDelete, placeholder = "选择或输入路径" }: PathInputProps) {
  const handleBrowse = useCallback(async () => {
    try {
      const res = await api.browseFolder();
      if (res.path) onChange(res.path);
    } catch { /* 用户取消 */ }
  }, [onChange]);

  return (
    <div className="group flex gap-1.5 items-center">
      <button onClick={handleBrowse} title="选择文件夹"
        className="w-8 h-[36px] flex items-center justify-center rounded-lg bg-white/[0.04] border border-white/[0.06] hover:bg-white/[0.08] transition-all flex-shrink-0">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-slate-400">
          <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
        </svg>
      </button>
      <div className="flex-1 flex items-center bg-white/[0.04] border border-white/[0.06] rounded-lg overflow-hidden focus-within:border-blue-500/30">
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
        {onDelete && (
          <button onClick={onDelete}
            className="w-7 h-7 flex items-center justify-center text-red-400/0 group-hover:text-red-400/60 hover:!text-red-400 transition-all flex-shrink-0 mr-0.5">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        )}
      </div>
    </div>
  );
}
