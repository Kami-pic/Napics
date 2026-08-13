// 详情面板通用小组件集合：EditableTitle、Poster、InfoRow、TipButton、MoveAction、CopyAction、DeleteAction、ConfidenceBadge、ScrapeInfo
"use client";
import { useState, useEffect } from "react";
import type { ScrapeResult, MatchConfidence } from "@/types";
import { api } from "@/lib/api";
import { BASE_URL } from "@/lib/api/base";

// ── 可编辑标题 ──
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

// ── 封面组件 ──
export function Poster({ url, fallbackName, localPath, aspect = "video", posterDeleted = false, noScrape = false }: { url?: string | null; fallbackName: string; localPath?: string; aspect?: "video" | "poster"; posterDeleted?: boolean; noScrape?: boolean }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const [remoteSrc, setRemoteSrc] = useState<string | null>(null);
  const [stage, setStage] = useState<"local" | "remote" | "done">(posterDeleted ? "done" : "local");
  const [cacheBust] = useState(() => Date.now());
  const localSrc = localPath ? api.getLocalPoster(localPath, noScrape) + `&_t=${cacheBust}` : null;
  const src = stage === "local" ? localSrc : stage === "remote" ? remoteSrc : null;
  const cls = aspect === "poster" ? "aspect-[2/3] max-h-[260px] mx-auto" : "aspect-video";
  useEffect(() => { setLoaded(false); setError(false); setRemoteSrc(null); setStage(posterDeleted ? "done" : "local"); }, [localPath, fallbackName, posterDeleted]);
  return (
    <div className={`${cls} rounded-xl overflow-hidden bg-[#222] relative`}>
      {!loaded && !error && stage !== "done" && src && <div className="absolute inset-0 flex items-center justify-center"><div className="w-6 h-6 border-2 border-slate-800 border-t-slate-500 rounded-full animate-spin" /></div>}
      {(stage === "done" || (!src && stage !== "local")) && <div className="absolute inset-0 bg-[#1a1a1a] flex items-center justify-center"><span className="text-slate-700 text-3xl">🎬</span></div>}
      {src && stage !== "done" && <img src={src} alt="" className={`w-full h-full object-cover transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-0"}`}
        onLoad={() => setLoaded(true)}
        onError={() => {
          if (stage === "local" && localPath && !posterDeleted && !noScrape) {
            // 本地封面不存在，尝试从 NFO 读远程封面 URL（仅末端刮削单元）
            setStage("done");
            api.readScrape(localPath, true).then(r => {
              if (r.status === "ok" && r.data?.poster_url) {
                // 通过后端代理加载远程封面（走 HTTP 代理）
                const proxyUrl = `${BASE_URL}/proxy/image?url=${encodeURIComponent(r.data.poster_url)}`;
                setRemoteSrc(proxyUrl);
                setStage("remote"); setLoaded(false); setError(false);
              }
            }).catch(() => {});
          } else { setStage("done"); }
        }} />}
    </div>
  );
}

// ── 信息行 ──
export function InfoRow({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center justify-between py-2 px-1 border-b border-white/[0.03] cursor-pointer" onClick={() => { navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); }} title="点击复制">
      <span className="text-sm text-slate-500">{label}</span>
      <span className={`text-sm truncate max-w-[200px] text-right ${warn ? "text-orange-400" : "text-slate-300"}`}>{copied ? <span className="text-green-400 text-xs">已复制</span> : value}</span>
    </div>
  );
}

// ── 提示按钮 ──
export function TipButton({ icon, label, tip, onClick }: { icon: string; label: string; tip: string; onClick?: () => void }) {
  return (
    <button onClick={onClick} className="w-full py-2.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-sm text-slate-300 transition-all text-left px-4 flex items-center gap-2.5 group relative">
      <span>{icon}</span><span>{label}</span>
      <div className="absolute left-0 bottom-full mb-2 px-3 py-2 bg-[#222] border border-white/[0.08] rounded-lg text-xs text-slate-400 w-64 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 shadow-xl">{tip}</div>
    </button>
  );
}

// ── 移动操作 ──
export function MoveAction({ onMove }: { onMove: (t: string) => void }) {
  const [show, setShow] = useState(false);
  const [target, setTarget] = useState("");
  if (!show) return <button onClick={() => setShow(true)} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-300">移动到</button>;
  return (<div className="col-span-4 flex gap-2"><input value={target} onChange={e => setTarget(e.target.value)} placeholder="目标路径" autoFocus onBlur={() => setTimeout(() => setShow(false), 150)} className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs outline-none text-slate-300" onKeyDown={e => { if (e.key === "Enter" && target) { onMove(target); setShow(false); } if (e.key === "Escape") setShow(false); }} /><button onMouseDown={e => e.preventDefault()} onClick={() => { if (target) { onMove(target); setShow(false); } }} className="px-3 py-2 rounded-lg bg-blue-500/20 text-blue-400 text-xs">确定</button></div>);
}

// ── 复制操作 ──
export function CopyAction({ onCopy }: { onCopy: (t: string) => void }) {
  const [show, setShow] = useState(false);
  const [target, setTarget] = useState("");
  if (!show) return <button onClick={() => setShow(true)} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-300">复制到</button>;
  return (<div className="col-span-4 flex gap-2"><input value={target} onChange={e => setTarget(e.target.value)} placeholder="目标路径" autoFocus onBlur={() => setTimeout(() => setShow(false), 150)} className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs outline-none text-slate-300" onKeyDown={e => { if (e.key === "Enter" && target) { onCopy(target); setShow(false); } if (e.key === "Escape") setShow(false); }} /><button onMouseDown={e => e.preventDefault()} onClick={() => { if (target) { onCopy(target); setShow(false); } }} className="px-3 py-2 rounded-lg bg-blue-500/20 text-blue-400 text-xs">确定</button></div>);
}

// ── 删除操作 ──
export function DeleteAction({ onDelete }: { onDelete: () => void }) {
  const [confirm, setConfirm] = useState(false);
  useEffect(() => { if (confirm) { const t = setTimeout(() => setConfirm(false), 3000); return () => clearTimeout(t); } }, [confirm]);
  if (!confirm) return <button onClick={() => setConfirm(true)} className="py-2 rounded-lg bg-white/[0.04] hover:bg-red-500/10 text-xs text-red-400">删除</button>;
  return (<div className="col-span-4 flex items-center gap-2 bg-red-500/5 border border-red-500/20 rounded-lg p-2.5"><span className="text-xs text-red-400 flex-1">确定删除？</span><button onClick={() => { onDelete(); setConfirm(false); }} className="px-3 py-1 rounded bg-red-600 text-white text-xs">删除</button><button onClick={() => setConfirm(false)} className="px-2 py-1 text-xs text-slate-500">取消</button></div>);
}

// ── 置信度展示 ──
export function ConfidenceBadge({ confidence, pendingConfirm, onConfirm, onReject }: {
  confidence: MatchConfidence | null;
  pendingConfirm: boolean;
  onConfirm: () => void;
  onReject: () => void;
}) {
  if (!confidence) return null;
  const { level, score, details } = confidence;
  const colors = { high: "text-green-400 bg-green-500/10 border-green-500/20", medium: "text-amber-400 bg-amber-500/10 border-amber-500/20", low: "text-red-400 bg-red-500/10 border-red-500/20" };
  const labels = { high: "高置信度", medium: "中置信度", low: "低置信度" };

  return (
    <div className={`rounded-lg border p-2.5 space-y-2 ${colors[level]}`}>
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium">{labels[level]} ({score}分)</span>
        {level === "high" && <span className="text-[10px]">✓ 自动采用</span>}
      </div>
      {details && Object.keys(details).length > 0 && (
        <div className="flex flex-wrap gap-1">
          {Object.entries(details).map(([k, v]) => (
            <span key={k} className="text-[9px] px-1.5 py-0.5 rounded bg-white/[0.04]">{k}: {v > 0 ? "+" : ""}{v}</span>
          ))}
        </div>
      )}
      {level === "medium" && pendingConfirm && (
        <div className="flex gap-2 pt-1">
          <button onClick={onConfirm} className="flex-1 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-xs text-amber-400 font-medium">确认采用</button>
          <button onClick={onReject} className="px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.06] text-xs text-slate-500">重新匹配</button>
        </div>
      )}
      {level === "low" && pendingConfirm && (
        <div className="pt-1">
          <p className="text-[10px] mb-1.5">置信度较低，建议手动选择匹配</p>
          <button onClick={onReject} className="w-full py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.06] text-xs text-slate-400">打开候选列表</button>
        </div>
      )}
    </div>
  );
}

// ── 刮削信息展示 ──
export function ScrapeInfo({ data }: { data: ScrapeResult }) {
  if (!data.tmdb_id && !data.title) return null;
  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-center gap-2">{data.year && <span className="text-xs text-slate-500">{data.year}</span>}{data.rating > 0 && <span className="text-xs text-amber-400">★ {data.rating}</span>}{data.media_type === "tv" && data.status && <span className={`text-[10px] px-1.5 py-0.5 rounded ${data.status === "Ended" ? "bg-slate-700 text-slate-400" : "bg-green-500/20 text-green-400"}`}>{data.status === "Ended" ? "已完结" : "连载中"}</span>}</div>
        {data.english_title && data.english_title !== data.title && <p className="text-xs text-blue-400/70 mt-1">{data.english_title}</p>}
        {data.original_title && data.original_title !== data.title && data.original_title !== data.english_title && <p className="text-xs text-slate-600 mt-0.5">{data.original_title}</p>}
      </div>
      {data.genres?.length > 0 && <div className="flex flex-wrap gap-1.5">{data.genres.map(g => <span key={g} className="text-[11px] px-2 py-0.5 rounded-md bg-white/[0.04] text-slate-400">{g}</span>)}</div>}
      {data.overview && <p className="text-sm text-slate-400 leading-relaxed">{data.overview}</p>}
      {data.media_type === "movie" && <div className="space-y-1">{data.director && <InfoRow label="导演" value={data.director} />}{data.cast?.length > 0 && <InfoRow label="主演" value={data.cast.join(" / ")} />}{data.runtime > 0 && <InfoRow label="时长" value={data.runtime + " 分钟"} />}</div>}
      {data.media_type === "tv" && data.total_seasons > 0 && <InfoRow label="总季数" value={data.total_seasons + " 季"} />}
    </div>
  );
}
