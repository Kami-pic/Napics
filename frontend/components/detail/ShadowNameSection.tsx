// 标准化名称管理区：显示/编辑标准化名称和搜索索引名称
"use client";
import { useState, useEffect } from "react";
import type { VideoInfo } from "@/types";
import { api } from "@/lib/api";
import { BASE_URL } from "@/lib/api/base";
import NameConflictHint from "./NameConflictHint";

export function ShadowNameSection({ path, video, folderName, folderShadowName, folderCleanName, cleanNameEn, onRefresh, onTreeRefresh }: { path: string; video?: VideoInfo; folderName?: string; folderShadowName?: string; folderCleanName?: string; cleanNameEn?: string; onRefresh?: () => void; onTreeRefresh?: () => void }) {
  // 文件夹模式：用 folderName/folderShadowName/folderCleanName；视频模式：用 video 字段
  const isFolder = !video && !!folderName;
  const fileName = video?.file_name || folderName || "";
  const shadowName = video?.shadow_name || folderShadowName || "";
  const cleanName = video?.clean_name || folderCleanName || "";
  const enName = cleanNameEn || video?.clean_name_en || "";
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [editingClean, setEditingClean] = useState(false);
  const [cleanEditValue, setCleanEditValue] = useState("");
  const [editingEn, setEditingEn] = useState(false);
  const [enEditValue, setEnEditValue] = useState("");

  useEffect(() => { setEditing(false); setEditingClean(false); setEditingEn(false); }, [path, video?.file_name]);

  if (!fileName) return null;

  const handleRename = async (newName: string) => {
    if (!newName.trim() || newName.trim() === fileName) { setEditing(false); return; }
    setSaving(true);
    try {
      // 文件和文件夹都只传新名字。这里以前给文件夹拼的是整条新路径
      // （parentDir + "\\" + newName），而后端把 new_name 当文件名用了好几处 ——
      // 最坑的是算新视频路径时 os.path.join(目录, 绝对路径) 直接返回后者，
      // 视频被搬出封装夹落到合集目录里。硬拼的反斜杠在 Linux 部署下还会造出
      // 名字里含 `\` 的目录。后端现在也会对 new_name 取 basename 兜底。
      await api.rename(path, newName.trim());
      setEditing(false);
      onRefresh?.();
    } catch (e: any) { alert("重命名失败: " + (e?.message || "")); }
    setSaving(false);
  };

  const handleApplyShadow = async () => {
    if (!shadowName) return;
    if (isFolder) {
      // 文件夹：用标准名替换文件夹名
      if (!confirm(`确定用标准名替换文件夹名？\n\n${fileName}\n→ ${shadowName}`)) return;
      await handleRename(shadowName);
    } else {
      const ext = fileName.includes(".") ? fileName.substring(fileName.lastIndexOf(".")) : "";
      const newName = shadowName + ext;
      if (!confirm(`确定用标准名替换原始文件名？\n\n${fileName}\n→ ${newName}`)) return;
      await handleRename(newName);
    }
  };

  const handleSaveShadow = async (newShadow: string) => {
    if (!newShadow.trim()) { setEditing(false); return; }
    setSaving(true);
    try {
      if (isFolder) {
        // 文件夹标准名：通过 shadow-name API 保存（用 path 作为 key）
        await fetch(`${BASE_URL}/media/shadow-name`, {
          method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({file_path: path, shadow_name: newShadow.trim(), source: "manual"})
        });
      } else if (video?.file_path) {
        await fetch(`${BASE_URL}/media/shadow-name`, {
          method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({file_path: video.file_path, shadow_name: newShadow.trim(), source: "manual"})
        });
      }
      setEditing(false);
      if (isFolder) {
        onTreeRefresh?.();
      } else {
        onRefresh?.();
      }
    } catch (e: any) { alert("保存标准名失败: " + (e?.message || "")); }
    setSaving(false);
  };

  const handleSaveClean = async (newClean: string) => {
    const filePath = video?.file_path || path;
    if (!newClean.trim() || !filePath) { setEditingClean(false); return; }
    try {
      await fetch(`${BASE_URL}/library/clean-name`, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({file_path: filePath, clean_name: newClean.trim(), is_folder: isFolder})
      });
      setEditingClean(false);
      if (isFolder) { onTreeRefresh?.(); } else { onRefresh?.(); }
    } catch { alert("保存失败"); }
  };

  const handleSaveEn = async (newEn: string) => {
    const filePath = video?.file_path || path;
    if (!filePath) { setEditingEn(false); return; }
    try {
      await fetch(`${BASE_URL}/library/clean-name`, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({file_path: filePath, clean_name_en: newEn.trim(), is_folder: isFolder})
      });
      setEditingEn(false);
      if (isFolder) { onTreeRefresh?.(); } else { onRefresh?.(); }
    } catch { alert("保存失败"); }
  };

  if (editing) {
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-1.5 px-1">
          <span className="text-[10px] text-slate-600 flex-shrink-0">✨</span>
          <input value={editValue} onChange={e => setEditValue(e.target.value)} autoFocus
            onKeyDown={e => { if (e.key === "Enter") handleSaveShadow(editValue); if (e.key === "Escape") setEditing(false); }}
            onBlur={() => { setTimeout(() => setEditing(false), 150); }}
            className="flex-1 bg-white/[0.06] border border-white/[0.08] rounded px-2 py-0.5 text-xs text-white outline-none focus:border-blue-500/40 min-w-0"
            placeholder="输入标准化名称" />
          <button onMouseDown={e => e.preventDefault()} onClick={() => handleSaveShadow(editValue)} disabled={saving} className="text-[10px] text-blue-400 flex-shrink-0">{saving ? "..." : "保存"}</button>
          <button onClick={() => setEditing(false)} className="text-[10px] text-slate-600 flex-shrink-0">取消</button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {/* 名字没通过自检时先说清楚，别让候选值被当成可信数据 */}
      <NameConflictHint conflicts={video?.name_conflicts} />
      {/* 标准化名称 */}
      <div className="flex items-center gap-2 px-1">
        <span className="text-[10px] text-slate-600">✨</span>
        {shadowName ? (
          <>
            <span className="text-xs text-slate-400 truncate flex-1 cursor-pointer hover:text-slate-300"
              onClick={() => { setEditValue(shadowName); setEditing(true); }} title="点击编辑标准化名称">{shadowName}</span>
            {shadowName !== (isFolder ? fileName : fileName.replace(/\.[^.]+$/, '')) && (
              <button onClick={handleApplyShadow} className="text-[10px] text-amber-500/70 hover:text-amber-400 flex-shrink-0" title="用标准名替换原始名">替换原始名</button>
            )}
          </>
        ) : (
          <span className="text-xs text-slate-600 truncate flex-1 cursor-pointer hover:text-slate-400"
            onClick={() => { setEditValue(fileName.replace(/\.[^.]+$/, '')); setEditing(true); }} title="点击设置标准化名称">{fileName}</span>
        )}
      </div>
      {/* 搜索索引名称（中文 + 英文同一行，各自可独立编辑） */}
      <div className="flex items-center gap-2 px-1">
        <span className="text-[10px] text-slate-600 flex-shrink-0">🧹</span>
        {editingClean ? (
          <div className="flex items-center gap-1.5 flex-1">
            <input value={cleanEditValue} onChange={e => setCleanEditValue(e.target.value)} autoFocus
              onKeyDown={e => { if (e.key === "Enter") handleSaveClean(cleanEditValue); if (e.key === "Escape") setEditingClean(false); }}
              onBlur={() => setTimeout(() => setEditingClean(false), 150)}
              className="flex-1 bg-white/[0.06] border border-white/[0.08] rounded px-2 py-0.5 text-[11px] text-white outline-none focus:border-blue-500/40 min-w-0" />
            <button onMouseDown={e => e.preventDefault()} onClick={() => handleSaveClean(cleanEditValue)} className="text-[10px] text-blue-400 flex-shrink-0">保存</button>
          </div>
        ) : editingEn ? (
          <div className="flex items-center gap-1.5 flex-1">
            <input value={enEditValue} onChange={e => setEnEditValue(e.target.value)} autoFocus
              onKeyDown={e => { if (e.key === "Enter") handleSaveEn(enEditValue); if (e.key === "Escape") setEditingEn(false); }}
              onBlur={() => setTimeout(() => setEditingEn(false), 150)}
              placeholder="英文名"
              className="flex-1 bg-white/[0.06] border border-white/[0.08] rounded px-2 py-0.5 text-[11px] text-white outline-none focus:border-blue-500/40 min-w-0" />
            <button onMouseDown={e => e.preventDefault()} onClick={() => handleSaveEn(enEditValue)} className="text-[10px] text-blue-400 flex-shrink-0">保存</button>
          </div>
        ) : (
          <span className="text-[11px] truncate flex-1">
            {cleanName ? (
              <span className="text-slate-600 cursor-pointer hover:text-slate-400" onClick={() => { setCleanEditValue(cleanName); setEditingClean(true); }} title="点击编辑搜索索引名称">{cleanName}</span>
            ) : (
              <span className="text-slate-600">未设置</span>
            )}
            {enName && !cleanName.includes(enName) ? (
              <span className="text-slate-700 ml-1 cursor-pointer hover:text-slate-400" onClick={() => { setEnEditValue(enName); setEditingEn(true); }} title="点击编辑英文名">{enName}</span>
            ) : !enName ? (
              <span className="text-slate-800 ml-1 cursor-pointer hover:text-slate-500" onClick={() => { setEnEditValue(""); setEditingEn(true); }} title="点击添加英文名">+ en</span>
            ) : null}
          </span>
        )}

      </div>
    </div>
  );
}
