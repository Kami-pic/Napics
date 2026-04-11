// 海报上传/删除组件：支持 URL 拉取、删除封面、删除刮削数据
"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export function PosterUpload({ path, onUploaded, hideDeleteScrape = false }: { path: string; onUploaded: (deleted?: boolean) => void; hideDeleteScrape?: boolean }) {
  const [showInput, setShowInput] = useState(false);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!url.trim()) return;
    setLoading(true);
    try {
      await api.setPosterFromUrl(path, url.trim(), hideDeleteScrape);
      setUrl(""); setShowInput(false); onUploaded(false);
    } catch { alert("拉取失败"); }
    setLoading(false);
  };

  const handleDeletePoster = async () => {
    try {
      const res = await api.deletePoster(path);
      onUploaded(true);
    } catch { alert("删除失败"); }
  };

  const handleDeleteScrape = async () => {
    if (!confirm("确定删除刮削数据（NFO+封面）？")) return;
    try { await api.deleteScrape(path); onUploaded(true); } catch { alert("删除失败"); }
  };

  if (showInput) {
    return (
      <div className="flex flex-col gap-1.5 bg-black/60 backdrop-blur rounded-lg p-2 min-w-[200px]">
        <input value={url} onChange={e => setUrl(e.target.value)} placeholder="输入图片 URL"
          onKeyDown={e => e.key === "Enter" && handleSubmit()}
          className="bg-white/10 border border-white/10 rounded px-2 py-1 text-xs text-white outline-none focus:border-blue-500/50 w-full" autoFocus />
        <div className="flex gap-1.5">
          <button onClick={handleSubmit} disabled={loading} className="flex-1 py-1 rounded bg-blue-600/80 text-xs text-white disabled:opacity-50">{loading ? "..." : "确定"}</button>
          <button onClick={() => setShowInput(false)} className="flex-1 py-1 rounded bg-white/10 text-xs text-slate-400">取消</button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-1.5">
      <button onClick={() => setShowInput(true)} className="text-xs text-blue-400 hover:text-blue-300 bg-black/40 backdrop-blur rounded px-2 py-1">换封面</button>
      <button onClick={handleDeletePoster} className="text-xs text-red-400 hover:text-red-300 bg-black/40 backdrop-blur rounded px-2 py-1">删封面</button>
      {!hideDeleteScrape && <button onClick={handleDeleteScrape} className="text-xs text-orange-400 hover:text-orange-300 bg-black/40 backdrop-blur rounded px-2 py-1">删刮削</button>}
    </div>
  );
}
