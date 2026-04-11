// 可编辑标题组件
"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export function EditableTitle({ name, path, onRenamed }: { name: string; path: string; onRenamed: () => void }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(name);
  const [saving, setSaving] = useState(false);

  // name 变化时同步 value
  useEffect(() => {
    setValue(name);
    setEditing(false);
  }, [name, path]);

  const handleSave = async () => {
    const trimmed = value.trim();
    if (!trimmed || trimmed === name) { setEditing(false); return; }
    setSaving(true);
    try {
      await api.rename(path, trimmed);
      onRenamed();
      setEditing(false);
    } catch (e: any) {
      alert("重命名失败: " + (e.message || ""));
    }
    setSaving(false);
  };

  if (editing) {
    return (
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <input value={value} onChange={e => setValue(e.target.value)} autoFocus
          onKeyDown={e => { if (e.key === "Enter") handleSave(); if (e.key === "Escape") { setEditing(false); setValue(name); } }}
          onBlur={() => { setTimeout(() => { setEditing(false); setValue(name); }, 150); }}
          className="flex-1 bg-white/[0.06] border border-white/[0.1] rounded-lg px-3 py-1.5 text-sm text-white outline-none focus:border-blue-500/40 min-w-0" />
        <button onMouseDown={e => e.preventDefault()} onClick={handleSave} disabled={saving} className="text-xs text-blue-400 hover:text-blue-300 flex-shrink-0">{saving ? "..." : "保存"}</button>
        <button onMouseDown={e => e.preventDefault()} onClick={() => { setEditing(false); setValue(name); }} className="text-xs text-slate-500 flex-shrink-0">取消</button>
      </div>
    );
  }

  return (
    <h3 className="text-base font-semibold text-slate-200 truncate pr-3 cursor-pointer hover:text-white group flex items-center gap-2 flex-1 min-w-0"
      onClick={() => setEditing(true)} title="点击重命名">
      <span className="truncate">{name}</span>
      <svg className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400 flex-shrink-0 transition-colors" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
    </h3>
  );
}

// ── 文件夹详情 ──
