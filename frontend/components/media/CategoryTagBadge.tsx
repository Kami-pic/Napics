// 一级分类标签 — 可点击切换类型
"use client";
import React, { useState, useRef, useEffect } from "react";
import { getCategoryTagLabel, CATEGORY_TAG_LABELS } from "@/lib/folderTypes";
import { BASE_URL } from "@/lib/api/base";

interface CategoryTagBadgeProps {
  tag: string;
  editable: boolean;
  path: string;
  onChanged?: () => void;
}

const TAG_OPTIONS = Object.entries(CATEGORY_TAG_LABELS);

export default function CategoryTagBadge({ tag, editable, path, onChanged }: CategoryTagBadgeProps) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const isMovie = tag === "movie" || tag === "anime_movie";
  const colorClass = isMovie ? "bg-blue-500/30 text-blue-300" : "bg-green-500/30 text-green-300";

  const handleSelect = async (newTag: string) => {
    if (newTag === tag) { setOpen(false); return; }
    setSaving(true);
    try {
      await fetch(`${BASE_URL}/library/category-tag`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, tag: newTag }),
      });
      setOpen(false);
      onChanged?.();
    } catch (e) {
      console.error("设置分类标签失败", e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div ref={ref} className="absolute top-3 left-3 z-20" onClick={e => e.stopPropagation()}>
      <button
        onClick={() => editable && setOpen(!open)}
        className={`text-[11px] px-2 py-0.5 rounded-md font-medium tracking-wide transition-all ${colorClass} ${editable ? "cursor-pointer hover:ring-1 hover:ring-white/20" : "cursor-default"}`}
        title={editable ? "点击切换分类" : ""}
      >
        {getCategoryTagLabel(tag)}{editable && " ▾"}
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-28 rounded-lg border border-white/[0.1] bg-[#1e1e1e] shadow-xl overflow-hidden">
          {TAG_OPTIONS.map(([value, label]) => (
            <button
              key={value}
              onClick={() => handleSelect(value)}
              disabled={saving}
              className={`w-full px-3 py-1.5 text-left text-[11px] transition-colors ${
                value === tag ? "text-blue-400 bg-blue-500/10" : "text-slate-300 hover:bg-white/[0.06]"
              } disabled:opacity-50`}
            >
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
