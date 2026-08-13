// 刮削候选面板：多源搜索与手动选择匹配（Tab 列表从 provider metadata 驱动）
"use client";
import { useState, useEffect, useMemo } from "react";
import { getMediaTypeColor, getRatingColor } from "@/lib/mediaColors";
import { api } from "@/lib/api";
import { BASE_URL } from "@/lib/api/base";
import type { ProviderCatalog, ProviderMetadata } from "@/types";

/** metadata provider id → Tab 颜色 */
const TAB_COLORS: Record<string, { active: string; rating: "tmdb" | "douban" | "bangumi" }> = {
  tmdb: { active: "bg-blue-500/20 text-blue-400", rating: "tmdb" },
  douban: { active: "bg-green-500/20 text-green-400", rating: "douban" },
  bangumi: { active: "bg-pink-500/20 text-pink-400", rating: "bangumi" },
};
const DEFAULT_TAB_COLOR = { active: "bg-slate-500/20 text-slate-400", rating: "tmdb" as const };

/** 默认 Tab 顺序（provider 接口失败时的 fallback） */
const FALLBACK_TABS: { id: string; name: string }[] = [
  { id: "tmdb", name: "TMDB" },
  { id: "douban", name: "豆瓣" },
  { id: "bangumi", name: "Bangumi" },
];

/** 根据错误类型生成友好提示 */
function getSearchErrorHint(e: any): string {
  const msg = e?.message || String(e) || "";
  if (msg.includes("429") || msg.includes("限频") || msg.includes("rate")) return "请求过于频繁，请稍后重试";
  if (msg.includes("timeout") || msg.includes("超时")) return "请求超时，请检查网络或代理配置";
  if (msg.includes("proxy") || msg.includes("ECONNREFUSED") || msg.includes("网络")) return "网络连接失败，请检查代理配置";
  if (msg.includes("401") || msg.includes("api_key")) return "API Key 无效，请在设置中检查";
  return "搜索失败，请稍后重试";
}

export function CandidatePicker({ name, path, onSelected }: { name: string; path: string; onSelected: (data?: any) => void }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("");
  const [candidates, setCandidates] = useState<any[]>([]);
  const [doubanCandidates, setDoubanCandidates] = useState<any[]>([]);
  const [bangumiCandidates, setBangumiCandidates] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selecting, setSelecting] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchError, setSearchError] = useState("");
  const [metadataProviders, setMetadataProviders] = useState<ProviderMetadata[]>([]);
  const [defaultSource, setDefaultSource] = useState("tmdb");

  // 加载 metadata provider 列表 + 默认刮削源配置
  useEffect(() => {
    api.getProviders()
      .then((catalog: ProviderCatalog) => {
        if (catalog.metadata?.length > 0) setMetadataProviders(catalog.metadata);
      })
      .catch(() => { /* 使用 fallback */ });
    api.getConfig()
      .then((config: any) => {
        if (config.default_scrape_source) setDefaultSource(config.default_scrape_source);
      })
      .catch(() => {});
  }, []);

  // 从 provider metadata 构建 Tab 列表，默认刮削源排第一
  const tabs = useMemo(() => {
    let list: { id: string; name: string }[];
    if (metadataProviders.length > 0) {
      list = metadataProviders.map(p => ({ id: p.id, name: p.name }));
    } else {
      list = [...FALLBACK_TABS];
    }
    // 将默认刮削源排到第一位
    const idx = list.findIndex(t => t.id === defaultSource);
    if (idx > 0) {
      const [item] = list.splice(idx, 1);
      list.unshift(item);
    }
    return list;
  }, [metadataProviders, defaultSource]);

  const searchTmdb = async (q?: string) => {
    setLoading(true); setSearchError("");
    try { const r = await api.scrapeCandidates(q || searchQuery || name); setCandidates(r.candidates || []); }
    catch (e: any) { setCandidates([]); setSearchError(getSearchErrorHint(e)); }
    setLoading(false);
  };
  const searchDouban = async (q?: string) => {
    setLoading(true); setSearchError("");
    try { const r = await api.scrapeDoubanCandidates(q || searchQuery || name); setDoubanCandidates(r.candidates || []); }
    catch (e: any) { setDoubanCandidates([]); setSearchError(getSearchErrorHint(e)); }
    setLoading(false);
  };
  const searchBangumi = async (q?: string) => {
    setLoading(true); setSearchError("");
    try { const r = await api.scrapeBangumiCandidates(q || searchQuery || name); setBangumiCandidates(r.candidates || []); }
    catch (e: any) { setBangumiCandidates([]); setSearchError(getSearchErrorHint(e)); }
    setLoading(false);
  };

  const searchByTab = async (t: string, q?: string) => {
    const query = q || searchQuery || name;
    if (t === "tmdb") await searchTmdb(query);
    else if (t === "douban") await searchDouban(query);
    else if (t === "bangumi") await searchBangumi(query);
  };

  const getCandidatesByTab = (t: string) => {
    if (t === "tmdb") return candidates;
    if (t === "douban") return doubanCandidates;
    if (t === "bangumi") return bangumiCandidates;
    return [];
  };

  const openPanel = async () => {
    const initialTab = defaultSource || "tmdb";
    setOpen(true); setTab(initialTab); setSearchQuery(name);
    setLoading(true);
    try {
      if (initialTab === "douban") {
        const r = await api.scrapeDoubanCandidates(name);
        setDoubanCandidates(r.candidates || []);
      } else if (initialTab === "bangumi") {
        const r = await api.scrapeBangumiCandidates(name);
        setBangumiCandidates(r.candidates || []);
      } else {
        const r = await api.scrapeCandidates(name);
        setCandidates(r.candidates || []);
        if (r.query) setSearchQuery(r.query);
      }
    } catch {
      if (initialTab === "douban") setDoubanCandidates([]);
      else if (initialTab === "bangumi") setBangumiCandidates([]);
      else setCandidates([]);
    }
    setLoading(false);
  };

  const switchTab = async (t: string) => {
    setTab(t);
    if (getCandidatesByTab(t).length === 0) await searchByTab(t);
  };

  const reSearch = async () => {
    const q = searchQuery.trim();
    if (!q) return;
    setCandidates([]); setDoubanCandidates([]); setBangumiCandidates([]);
    await searchByTab(tab, q);
  };

  const selectTmdb = async (c: any) => {
    setSelecting(`tmdb-${c.tmdb_id}`);
    try { const r = await api.scrapeSelect(path, c.tmdb_id, c.media_type); setOpen(false); onSelected(r.data); } catch (e: any) { alert("写入失败: " + (e?.message || e)); }
    setSelecting(null);
  };
  const selectDouban = async (c: any) => {
    setSelecting(`douban-${c.douban_id}`);
    try { const r = await api.scrapeDoubanSelect(path, c.douban_id, c.title, c.year, c.poster_url_original || c.poster_url, c.subtitle); setOpen(false); onSelected(r.data); } catch (e: any) { alert("写入失败: " + (e?.message || e)); }
    setSelecting(null);
  };
  const selectBangumi = async (c: any) => {
    setSelecting(`bgm-${c.bgm_id}`);
    try { const r = await api.scrapeBangumiSelect(path, c.bgm_id); setOpen(false); onSelected(r.data); } catch (e: any) { alert("写入失败: " + (e?.message || e)); }
    setSelecting(null);
  };

  if (!open) return <button onClick={openPanel} className="py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-xs text-amber-400">重新匹配</button>;

  const currentList = getCandidatesByTab(tab);
  const tabColor = TAB_COLORS[tab] || DEFAULT_TAB_COLOR;

  return (
    <div className="col-span-full bg-[#141414] border border-white/[0.06] rounded-xl p-3 space-y-2">
      <div className="flex gap-2">
        <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === "Enter" && reSearch()}
          placeholder="编辑搜索词..."
          className="flex-1 bg-white/[0.06] border border-white/[0.06] rounded-lg px-2.5 py-1.5 text-xs text-white outline-none focus:border-blue-500/40" />
        <button onClick={reSearch} className="px-3 py-1.5 rounded-lg bg-blue-500/20 text-xs text-blue-400 hover:bg-blue-500/30">搜索</button>
        <button onClick={() => setOpen(false)} className="px-2 py-1.5 text-xs text-slate-600 hover:text-slate-400">✕</button>
      </div>
      <div className="flex gap-2">
        {tabs.map(t => {
          const color = TAB_COLORS[t.id] || DEFAULT_TAB_COLOR;
          return (
            <button key={t.id} onClick={() => switchTab(t.id)}
              className={`text-xs px-2.5 py-1 rounded-md transition-all ${tab === t.id ? color.active : "text-slate-500 hover:text-slate-300"}`}>
              {t.name}
            </button>
          );
        })}
      </div>
      {loading && <div className="flex justify-center py-4"><div className="w-5 h-5 border-2 border-slate-700 border-t-blue-400 rounded-full animate-spin" /></div>}
      {!loading && currentList.length === 0 && !searchError && <p className="text-xs text-slate-600 py-2">未找到候选</p>}
      {!loading && searchError && <p className="text-xs text-amber-400/80 py-2">⚠️ {searchError}</p>}
      <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
        {tab === "tmdb" && candidates.map(c => (
          <CandidateCardTmdb key={`tmdb-${c.tmdb_id}`} c={c} selecting={selecting} onSelect={selectTmdb} />
        ))}
        {tab === "douban" && doubanCandidates.map(c => (
          <CandidateCardDouban key={`db-${c.douban_id}`} c={c} selecting={selecting} onSelect={selectDouban} />
        ))}
        {tab === "bangumi" && bangumiCandidates.map(c => (
          <CandidateCardBangumi key={`bgm-${c.bgm_id}`} c={c} selecting={selecting} onSelect={selectBangumi} />
        ))}
      </div>
    </div>
  );
}

// ── 候选卡片子组件 ──

function CandidateCardTmdb({ c, selecting, onSelect }: { c: any; selecting: string | null; onSelect: (c: any) => void }) {
  return (
    <button onClick={() => onSelect(c)} disabled={selecting !== null}
      className={`w-full flex gap-2.5 p-2 rounded-lg text-left transition-all ${selecting === `tmdb-${c.tmdb_id}` ? "bg-blue-500/20 border border-blue-500/30" : "bg-white/[0.03] hover:bg-white/[0.06] border border-transparent"}`}>
      <CandidatePoster url={c.poster_url} />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-white truncate">{c.title}</p>
        {c.english_title && c.english_title !== c.title && <p className="text-[11px] text-blue-400/70 truncate">{c.english_title}</p>}
        {c.original_title && c.original_title !== c.title && c.original_title !== c.english_title && <p className="text-[11px] text-slate-500 truncate">{c.original_title}</p>}
        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
          {(() => { const mc = getMediaTypeColor(c.media_type); return <span className={`text-[10px] px-1.5 py-0.5 rounded ${mc.bg} ${mc.text}`}>{mc.label}</span>; })()}
          <span className="text-[10px] text-slate-600">{c.year}</span>
          {c.rating > 0 && <RatingBadge source="tmdb" rating={c.rating} />}
        </div>
        {c.overview && <p className="text-[11px] text-slate-600 mt-1 line-clamp-2 leading-relaxed">{c.overview}</p>}
      </div>
    </button>
  );
}

function CandidateCardDouban({ c, selecting, onSelect }: { c: any; selecting: string | null; onSelect: (c: any) => void }) {
  const posterUrl = c.poster_url?.startsWith("/") ? `${BASE_URL}${c.poster_url}` : c.poster_url;
  return (
    <button onClick={() => onSelect(c)} disabled={selecting !== null}
      className={`w-full flex gap-2.5 p-2 rounded-lg text-left transition-all ${selecting === `douban-${c.douban_id}` ? "bg-green-500/20 border border-green-500/30" : "bg-white/[0.03] hover:bg-white/[0.06] border border-transparent"}`}>
      <CandidatePoster url={posterUrl} referrerPolicy="no-referrer" />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-white truncate">{c.title}</p>
        {c.original_title && c.original_title !== c.title && <p className="text-[11px] text-slate-500 truncate">{c.original_title}</p>}
        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
          {c.media_type && (() => { const mc = getMediaTypeColor(c.media_type); return <span className={`text-[10px] px-1.5 py-0.5 rounded ${mc.bg} ${mc.text}`}>{mc.label}</span>; })()}
          {c.year && <span className="text-[10px] text-slate-600">{c.year}</span>}
          {c.rating > 0 && <RatingBadge source="douban" rating={c.rating} />}
          {c.countries?.length > 0 && <span className="text-[10px] text-slate-600">{c.countries.slice(0, 2).join("/")}</span>}
          {c.genres?.length > 0 && <span className="text-[10px] text-slate-600">{c.genres.slice(0, 3).join("/")}</span>}
        </div>
        <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
          {c.directors?.length > 0 && <span className="text-[10px] text-slate-600">导演: {c.directors.slice(0, 2).join(" / ")}</span>}
          {c.actors?.length > 0 && <span className="text-[10px] text-slate-600">主演: {c.actors.slice(0, 3).join(" / ")}</span>}
        </div>
        {c.overview && <p className="text-[11px] text-slate-600 mt-1 line-clamp-2 leading-relaxed">{c.overview}</p>}
      </div>
    </button>
  );
}

function CandidateCardBangumi({ c, selecting, onSelect }: { c: any; selecting: string | null; onSelect: (c: any) => void }) {
  return (
    <button onClick={() => onSelect(c)} disabled={selecting !== null}
      className={`w-full flex gap-2.5 p-2 rounded-lg text-left transition-all ${selecting === `bgm-${c.bgm_id}` ? "bg-pink-500/20 border border-pink-500/30" : "bg-white/[0.03] hover:bg-white/[0.06] border border-transparent"}`}>
      <CandidatePoster url={c.poster_url} referrerPolicy="no-referrer" />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-white truncate">{c.title}</p>
        {c.original_title && c.original_title !== c.title && <p className="text-[11px] text-slate-500 truncate">{c.original_title}</p>}
        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
          {(() => { const mc = getMediaTypeColor(c.type || "动画"); return <span className={`text-[10px] px-1.5 py-0.5 rounded ${mc.bg} ${mc.text}`}>{mc.label}</span>; })()}
          <span className="text-[10px] text-slate-600">{c.year}</span>
          {c.rating > 0 && <RatingBadge source="bangumi" rating={c.rating} />}
        </div>
        {c.summary && <p className="text-[11px] text-slate-600 mt-1 line-clamp-2">{c.summary}</p>}
      </div>
    </button>
  );
}

// ── 通用子组件 ──

function CandidatePoster({ url, referrerPolicy }: { url?: string; referrerPolicy?: string }) {
  return (
    <>
      {url ? <img src={url} alt="" referrerPolicy={referrerPolicy as any} className="w-10 h-14 rounded object-cover flex-shrink-0"
        onError={(e) => { const el = e.target as HTMLImageElement; el.style.display = "none"; el.parentElement?.querySelector("[data-fallback]")?.classList.remove("hidden"); }} />
      : null}
      <div data-fallback className={`w-10 h-14 rounded bg-[#222] flex-shrink-0 flex items-center justify-center ${url ? "hidden" : ""}`}><span className="text-slate-700 text-sm">🎬</span></div>
    </>
  );
}

function RatingBadge({ source, rating }: { source: "tmdb" | "douban" | "bangumi"; rating: number }) {
  return (
    <span className={`text-[10px] ${getRatingColor(source)} font-bold flex items-center gap-0.5`}>
      <svg className="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
      </svg>
      {rating}
    </span>
  );
}
