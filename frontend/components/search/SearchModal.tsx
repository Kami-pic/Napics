// BT 搜索结果弹窗 — V2：结构化三行布局 + 分组模式 + 命中关键词标注
"use client";
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import type { EnhancedSearchResult, FilterState, PanResult, PanSourceStatus } from "@/types";
import { api } from "@/lib/api";
import FilterBar, { DEFAULT_FILTERS, applyFilters } from "./FilterBar";

const RES_RANK: Record<string, number> = { "": 0, SD: 0, "720p": 1, "1080p": 2, "2160p": 3 };
type SearchTab = "bt" | "pan";

function normalizeResolution(raw?: string): string {
  if (!raw) return "";
  const l = raw.toLowerCase();
  if (l.includes("2160") || l.includes("4k")) return "2160p";
  if (l.includes("1080")) return "1080p";
  if (l.includes("720")) return "720p";
  return "SD";
}

interface SearchModalProps {
  open: boolean;
  query: string;
  onClose: () => void;
  defaultSavePath: string;
  currentResolution?: string;
  qbConfigured?: boolean;
  alistConfigured?: boolean;
  shadowName?: string;
  cleanName?: string;
  mediaType?: string;
  cnName?: string;       // 中文名
  enName?: string;       // 英文名
  folderType?: string;   // "tv" | "season" | "movie" 等
  seasonNumber?: number;  // 季号
  episodeTag?: string;    // 如 "S01E01"
}

export default function SearchModal({
  open, query, onClose, defaultSavePath,
  currentResolution, qbConfigured = true, alistConfigured = false,
  shadowName, cleanName, mediaType,
  cnName, enName, folderType, seasonNumber, episodeTag,
}: SearchModalProps) {
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<EnhancedSearchResult[]>([]);
  const [keyword, setKeyword] = useState(query);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{msg: string; ok: boolean} | null>(null);
  const [downloadingUrl, setDownloadingUrl] = useState<string | null>(null);
  const [hitKeyword, setHitKeyword] = useState("");
  const [totalRaw, setTotalRaw] = useState(0);
  const [smartFilter, setSmartFilter] = useState(false);  // 默认关闭过滤
  const [savePath, setSavePath] = useState(defaultSavePath);
  // 搜索标签系统（按确认的规则生成）
  const searchTags = useMemo(() => {
    const tags: { label: string; keyword: string }[] = [];
    const cn = (cnName || "").trim();
    const en = (enName || "").trim();
    const sNum = seasonNumber;
    const sTag = sNum ? `S${String(sNum).padStart(2, "0")}` : "";
    // cn 和 en 实质相同判断（忽略大小写和空格）
    const isSame = cn.toLowerCase() === en.toLowerCase();

    if (folderType === "season" && sNum) {
      if (cn) tags.push({ label: `${cn} 第${sNum}季`, keyword: `${cn} 第${sNum}季` });
      if (en && sTag && !isSame) tags.push({ label: `${en} ${sTag}`, keyword: `${en} ${sTag}` });
      if (cn && en && !isSame) tags.push({ label: `${cn} ${en}`, keyword: `${cn} ${en}` });
      if (cn) tags.push({ label: cn, keyword: cn });
      if (en && !isSame) tags.push({ label: en, keyword: en });
    } else if (episodeTag) {
      if (cn) tags.push({ label: `${cn} ${episodeTag}`, keyword: `${cn} ${episodeTag}` });
      if (en && !isSame) tags.push({ label: `${en} ${episodeTag}`, keyword: `${en} ${episodeTag}` });
      if (cn && en && !isSame) tags.push({ label: `${cn} ${en}`, keyword: `${cn} ${en}` });
      if (cn) tags.push({ label: cn, keyword: cn });
      if (en && !isSame) tags.push({ label: en, keyword: en });
    } else {
      if (cn && en && !isSame) tags.push({ label: `${cn} ${en}`, keyword: `${cn} ${en}` });
      if (cn) tags.push({ label: cn, keyword: cn });
      if (en && !isSame) tags.push({ label: en, keyword: en });
    }

    // 去重
    const seen = new Set<string>();
    return tags.filter(t => {
      const k = t.keyword.trim();
      if (!k || seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }, [cnName, enName, folderType, seasonNumber, episodeTag]);

  // 搜索结果缓存（弹窗关闭清除）
  const searchCache = useRef<Map<string, { results: EnhancedSearchResult[]; totalRaw: number }>>(new Map());
  const curRes = normalizeResolution(currentResolution);

  // ── 网盘搜索状态 ──
  const [activeTab, setActiveTab] = useState<SearchTab>("bt");
  const [panResults, setPanResults] = useState<PanResult[]>([]);
  const [panGroups, setPanGroups] = useState<Record<string, PanResult[]>>({});
  const [panSourceStatuses, setPanSourceStatuses] = useState<PanSourceStatus[]>([]);
  const [panSearching, setPanSearching] = useState(false);
  const [panTotal, setPanTotal] = useState(0);
  const panCache = useRef<Map<string, { results: PanResult[]; groups: Record<string, PanResult[]>; statuses: PanSourceStatus[]; total: number }>>(new Map());
  const [panFilters, setPanFilters] = useState<PanFilterState>(DEFAULT_PAN_FILTERS);

  useEffect(() => { setSavePath(defaultSavePath); }, [defaultSavePath]);
  useEffect(() => { setKeyword(query); }, [query]);
  useEffect(() => {
    if (open && query) doSearch(query);
    if (!open) {
      setResults([]); setError(""); setToast(null); setHitKeyword("");
      setFilters(DEFAULT_FILTERS); setDownloadingUrl(null);
      setSearchingStep(""); setSearching(false);
      searchCache.current.clear();
      setPanResults([]); setPanGroups({}); setPanSourceStatuses([]); setPanTotal(0); setPanSearching(false);
      panCache.current.clear();
      setActiveTab("bt");
    }
  }, [open, query]);

  const [searchingStep, setSearchingStep] = useState("");

  // 垃圾版本排除词（前端过滤用）
  const JUNK_PATTERNS = /\b(TS|CAM|HDTC|TC|TELECINE|HDTS|TELESYNC)\b/i;

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) return;

    // 检查缓存
    const cacheKey = q;
    const cached = searchCache.current.get(cacheKey);
    if (cached) {
      setResults(cached.results);
      setHitKeyword(q);
      setTotalRaw(cached.totalRaw);
      setKeyword(q);
      return;
    }

    setSearching(true); setResults([]); setError(""); setToast(null);
    setHitKeyword("");

    try {
      setKeyword(q);
      setSearchingStep(`搜索：${q}`);

      // 永远走 skip_filter=true，拿全部结果
      const d = await api.searchSingle(q, { skip_filter: true });
      const raw: EnhancedSearchResult[] = (d.bt_results || []).map((r: any) => ({
        ...r,
        quality: r.quality || { resolution: "", source: "", video_codec: "", audio_codec: "", has_chinese_sub: false, release_group: "", is_surround: false, display: r.quality_tag || "" },
        quality_rank: r.quality_rank ?? 0,
      }));

      // 写入缓存（只缓存有结果的）
      if (raw.length > 0) {
        searchCache.current.set(cacheKey, { results: raw, totalRaw: d.total_raw || raw.length });
      }

      setResults(raw);
      setHitKeyword(q);
      setTotalRaw(d.total_raw || raw.length);
    } catch {
      setError("搜索失败，请检查 Prowlarr 配置后重试");
    }
    setSearching(false);
    setSearchingStep("");
  }, []);

  // ── 网盘搜索 ──
  const doPanSearch = useCallback(async (q: string) => {
    if (!q.trim()) return;
    const cached = panCache.current.get(q);
    if (cached) {
      setPanResults(cached.results); setPanGroups(cached.groups);
      setPanSourceStatuses(cached.statuses); setPanTotal(cached.total);
      return;
    }
    setPanSearching(true); setPanResults([]); setPanGroups({});
    try {
      const d = await api.searchPan(q, mediaType);
      const results: PanResult[] = d.results || [];
      const groups: Record<string, PanResult[]> = d.groups || {};
      const statuses: PanSourceStatus[] = d.source_statuses || [];
      const total = d.total || 0;
      setPanResults(results); setPanGroups(groups);
      setPanSourceStatuses(statuses); setPanTotal(total);
      if (results.length > 0) {
        panCache.current.set(q, { results, groups, statuses, total });
      }
    } catch { setPanResults([]); }
    setPanSearching(false);
  }, [mediaType]);

  // 前端过滤：FilterBar 筛选 + 智能过滤（排除垃圾版本）
  const displayResults = useMemo(() => {
    let list = results;
    // 智能过滤开启时：排除 TS/CAM/HDTC 等垃圾版本
    if (smartFilter) {
      list = list.filter(r => !JUNK_PATTERNS.test(r.title));
    }
    return list;
  }, [results, smartFilter]);
  const filtered = applyFilters(displayResults, filters);
  const isHigher = (res: EnhancedSearchResult) => {
    const rr = RES_RANK[res.quality?.resolution ?? ""] ?? 0;
    const cr = RES_RANK[curRes] ?? 0;
    return cr > 0 && rr > cr;
  };

  const availableIndexers = useMemo(() => {
    const s = new Set<string>();
    results.forEach(r => { if (r.indexer) s.add(r.indexer); });
    return Array.from(s);
  }, [results]);

  const handleDownload = async (res: EnhancedSearchResult, channel: "qb" | "alist") => {
    setDownloadingUrl(res.download_url); setToast(null);
    try {
      const d = await api.submitDownload({
        media_name: query, download_url: res.download_url,
        save_path: savePath, channel,
      });
      if (d.success) { setToast({ msg: "任务已提交到下载队列", ok: true }); }
      else { setToast({ msg: "失败: " + (d.task?.error || "未知错误"), ok: false }); }
    } catch { setToast({ msg: "通信失败，请检查网络", ok: false }); }
    finally { setDownloadingUrl(null); }
  };

  if (!open) return null;

  // 判断是否为整季包（标题中含 SXX 但不含 EXX）
  const isSeasonPack = (title: string) => /S\d{2}/i.test(title) && !/E\d{2}/i.test(title);

  // 单条结果渲染（横条卡片）
  const renderResult = (res: EnhancedSearchResult, i: number) => {
    const higher = isHigher(res);
    const isDownloading = downloadingUrl === res.download_url;
    const q = res.quality;
    const surround = q?.is_surround ?? false;
    const is4k = q?.resolution === "2160p";
    const is1080 = q?.resolution === "1080p";
    const seasonPack = isSeasonPack(res.title);

    return (
      <div key={i} className="bg-[#0f0f0f] rounded-xl border border-white/[0.06] hover:border-white/[0.10] transition-colors overflow-hidden">
        <div className="flex items-center gap-4 px-4 py-3">
          {/* 左侧：标题 + 标签 */}
          <div className="flex-1 min-w-0">
            <p className="text-[13px] text-slate-200 truncate leading-snug" title={res.title}>{res.title}</p>
            <div className="flex items-center gap-1.5 mt-2 flex-wrap">
              {/* 分辨率：4K 金色，1080p 蓝色，720p 默认灰 */}
              {q?.resolution && (
                <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                  is4k ? "bg-yellow-500/20 text-yellow-400" :
                  is1080 ? "bg-blue-500/15 text-blue-400" :
                  "bg-white/[0.06] text-slate-500"
                }`}>{q.resolution}</span>
              )}
              {higher && <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/15 text-green-400 font-bold">↑ 更高</span>}
              {/* 来源 */}
              {q?.source && <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.04] text-slate-400">{q.source}</span>}
              {/* 视频编码（不高亮，默认灰色）*/}
              {q?.video_codec && <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.04] text-slate-500">{q.video_codec}</span>}
              {/* 音频编码：环绕声紫色高亮，普通灰色 */}
              {q?.audio_codec && (
                <span className={`text-[10px] px-2 py-0.5 rounded ${surround ? "bg-purple-500/15 text-purple-400 font-medium" : "bg-white/[0.04] text-slate-500"}`}>
                  {q.audio_codec}
                </span>
              )}
              {/* 索引器 */}
              <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.04] text-slate-500">{res.indexer}</span>
              {/* 中字高亮 */}
              {q?.has_chinese_sub && <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/15 text-blue-400 font-medium">中字</span>}
              {/* 整季包高亮 */}
              {seasonPack && <span className="text-[10px] px-2 py-0.5 rounded bg-yellow-500/15 text-yellow-400 font-medium">整季</span>}
              {/* 发布组 */}
              {q?.release_group && <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.04] text-slate-500">{q.release_group}</span>}
            </div>
          </div>
          {/* 右侧：大小 + 做种 + 下载按钮并排 */}
          <div className="flex items-center gap-4 flex-shrink-0">
            <div className="text-right min-w-[65px]">
              <p className="text-[13px] font-bold text-slate-200">{res.size_gb} GB</p>
              <p className="text-[11px] text-slate-500">
                做种 <span className={res.seeders > 10 ? "text-green-400" : res.seeders > 0 ? "text-yellow-400" : "text-red-400"}>{res.seeders}</span>
              </p>
            </div>
            <div className="flex gap-1.5">
              <button onClick={() => handleDownload(res, "qb")} disabled={!qbConfigured || isDownloading}
                className={`px-4 py-1.5 rounded-lg text-[12px] font-bold transition-colors ${qbConfigured ? "bg-blue-600 hover:bg-blue-500 text-white" : "bg-white/[0.04] text-slate-600 cursor-not-allowed"} disabled:opacity-40`}>
                {isDownloading ? "..." : "下载"}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-8 z-50">
      <div className="bg-[var(--background)] border border-white/[0.06] rounded-2xl w-full max-w-[1200px] max-h-[85vh] overflow-hidden flex flex-col">
        {/* 顶栏 */}
        <div className="p-5 border-b border-white/[0.06] space-y-3">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <h2 className="text-[15px] font-bold text-white">搜索资源</h2>
              {curRes && <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.06] text-slate-400">当前：{curRes}</span>}
              {hitKeyword && <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/10 text-blue-400">命中：{hitKeyword}</span>}
              {/* 搜索标签（点击快速切换搜索词）*/}
              {searchTags.length > 0 && searchTags.map((tag, ti) => (
                <button key={ti} onClick={() => doSearch(tag.keyword)}
                  className={`text-[10px] px-2 py-0.5 rounded transition-colors ${
                    keyword === tag.keyword ? "bg-blue-600/30 text-blue-300" : "bg-white/[0.04] text-slate-500 hover:text-slate-300 hover:bg-white/[0.06]"
                  }`}>{tag.label}</button>
              ))}
            </div>
            <button onClick={onClose} className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">✕</button>
          </div>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <input value={keyword} onChange={(e) => setKeyword(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { activeTab === "bt" ? doSearch(keyword) : doPanSearch(keyword); } }}
                placeholder="输入搜索关键词..."
                className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 pr-10 text-sm text-white outline-none focus:border-blue-500/50 placeholder:text-slate-600" />
              {/* 过滤器图标（搜索框内右侧，仅 BT 模式）*/}
              {activeTab === "bt" && (
                <button onClick={() => setSmartFilter(!smartFilter)}
                  title={smartFilter ? "智能过滤已开启" : "智能过滤已关闭"}
                  className={`absolute right-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded flex items-center justify-center text-sm transition-colors ${smartFilter ? "text-green-400 hover:bg-green-600/20" : "text-slate-600 hover:text-slate-400"}`}>
                  {smartFilter ? "🛡️" : "🔓"}
                </button>
              )}
            </div>
            <button onClick={() => { activeTab === "bt" ? doSearch(keyword) : doPanSearch(keyword); }} disabled={searching || panSearching}
              className={`px-5 py-2 rounded-lg text-[12px] font-bold transition-colors whitespace-nowrap disabled:opacity-50 ${
                activeTab === "bt" ? "bg-blue-600 hover:bg-blue-500 text-white" : "bg-emerald-600 hover:bg-emerald-500 text-white"
              }`}>
              {(searching || panSearching) ? "搜索中..." : "搜索"}
            </button>
          </div>
          {/* 保存路径移到底部 */}
          {/* 保存路径 + 通道切换（搜索框下方，同宽对齐） */}
          <div className="flex items-center gap-3">
            <div className="flex gap-2 flex-shrink-0">
              <button onClick={() => { setActiveTab("bt"); if (!results.length && keyword) doSearch(keyword); }}
                className={`px-8 py-2 rounded-lg text-[11px] font-bold transition-all active:scale-95 flex items-center gap-2 ${
                  activeTab === "bt" ? "bg-blue-600 text-white shadow-lg shadow-blue-500/20" : "bg-white/[0.06] text-slate-400 hover:bg-white/10"
                }`}>
                <span>🧲</span> BT / 磁力
              </button>
              <button onClick={() => { setActiveTab("pan"); if (!panResults.length && keyword) doPanSearch(keyword); }}
                className={`px-8 py-2 rounded-lg text-[11px] font-bold transition-all active:scale-95 flex items-center gap-2 ${
                  activeTab === "pan" ? "bg-emerald-600 text-white shadow-lg shadow-emerald-500/20" : "bg-white/[0.06] text-slate-400 hover:bg-white/10"
                }`}>
                <span>☁️</span> 网盘资源
              </button>
            </div>
            
            <div className="w-px h-6 bg-white/[0.06] mx-1" />
            
            <div className="flex-1 relative group">
              <input value={savePath} onChange={(e) => setSavePath(e.target.value)}
                placeholder="保存到：下载保存路径..."
                className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-blue-500/50 font-mono transition-all group-hover:bg-white/[0.06]"
                title={savePath} />
            </div>
          </div>
          {activeTab === "bt" && (
            <div className="flex items-center gap-2 flex-wrap">
              <FilterBar 
                filters={filters} 
                onChange={setFilters} 
                onClear={() => setFilters(DEFAULT_FILTERS)} 
                availableIndexers={availableIndexers}
              />
            </div>
          )}
          {activeTab === "pan" && (
            <PanFilterBar filters={panFilters} onChange={setPanFilters} groups={panGroups} sourceStatuses={panSourceStatuses} />
          )}
        </div>

        {toast && (
          <div className={`mx-5 mt-3 px-4 py-2 rounded-lg text-xs ${toast.ok ? "bg-green-500/10 text-green-400 border border-green-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"}`}>{toast.msg}</div>
        )}

        {/* 结果列表 */}
        <div className="flex-1 overflow-y-auto p-5">
          {activeTab === "bt" ? (
            /* ── BT/磁力 Tab ── */
            <>
          {searching ? (
            <div className="flex flex-col items-center py-16">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mb-3" />
              <p className="text-[13px] text-slate-500">{searchingStep || "搜罗全网资源..."}</p>
            </div>
          ) : error ? (
            <div className="text-center py-10">
              <p className="text-red-400 text-xs mb-3">{error}</p>
              <button onClick={() => doSearch(keyword)} className="text-xs text-blue-400 hover:text-blue-300">重试</button>
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.length > 0 && (
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[11px] text-slate-500">
                    共 {results.length} 条{smartFilter ? `，过滤后 ${displayResults.length} 条` : ""}{filtered.length !== displayResults.length ? `，筛选后 ${filtered.length} 条` : ""}
                  </p>
                </div>
              )}
              {/* 结果呈现 */}
              {filtered.map((res, i) => renderResult(res, i))}
              {filtered.length === 0 && results.length > 0 && (
                <p className="text-center py-10 text-xs text-slate-600">无匹配筛选条件的结果</p>
              )}
              {results.length === 0 && !searching && !error && (
                <p className="text-center py-10 text-xs text-slate-600">未搜到资源</p>
              )}
            </div>
          )}
            </>
          ) : (
            /* ── 网盘 Tab ── */
            <PanResultsView
              searching={panSearching}
              groups={panGroups}
              total={panTotal}
              sourceStatuses={panSourceStatuses}
              keyword={keyword}
              filters={panFilters}
              onRetry={() => doPanSearch(keyword)}
              onTransfer={async (r) => {
                setToast(null);
                try {
                  const result = await api.alistTransfer(r.share_url, r.pan_type, savePath);
                  if (result.success) {
                    setToast({ msg: "转存任务已提交", ok: true });
                  } else {
                    const errMap: Record<string, string> = {
                      disk_full: "网盘空间不足",
                      name_conflict: "同名文件已存在",
                      link_expired: "分享链接已失效",
                      wrong_password: "提取码错误",
                      alist_unavailable: "Alist 服务不可达",
                    };
                    setToast({ msg: errMap[result.error_code] || result.error_message || "转存失败", ok: false });
                  }
                } catch {
                  setToast({ msg: "转存请求失败", ok: false });
                }
              }}
            />
          )}
        </div>

        {/* 底部已移到顶栏搜索框下方 */}
      </div>
    </div>
  );
}


// ── 剧集搜索汇总表格（tv 模式）──
function EpisodeTable({
  episodeResults,
  seasonPacks,
  totalSizePack,
  totalSizeEpisode,
  recommendedPlan,
  onSelectAlternative,
}: {
  episodeResults: Record<number, import("@/types").EpisodeResult>;
  seasonPacks: import("@/types").SeasonPackInfo[];
  totalSizePack: number;
  totalSizeEpisode: number;
  recommendedPlan: string;
  onSelectAlternative: (ep: number, result: import("@/types").EnhancedSearchResult) => void;
}) {
  const [expandedEp, setExpandedEp] = useState<number | null>(null);
  const episodes = Object.entries(episodeResults)
    .map(([k, v]) => ({ ep: Number(k), ...v }))
    .sort((a, b) => a.ep - b.ep);

  const foundCount = episodes.filter(e => e.status === "found").length;
  const missingCount = episodes.filter(e => e.status === "not_found").length;

  return (
    <div className="space-y-3">
      {/* 方案 PK 对比 */}
      {seasonPacks.length > 0 && (
        <div className="flex items-center gap-4 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
          <div className="flex-1 text-center">
            <p className="text-[10px] text-slate-500 mb-1">整季包方案</p>
            <p className={`text-sm font-bold ${recommendedPlan === "season_pack" ? "text-green-400" : "text-slate-400"}`}>
              {totalSizePack} GB
            </p>
            <p className="text-[10px] text-slate-600">{seasonPacks.length} 个候选</p>
          </div>
          <span className="text-slate-600 text-xs">VS</span>
          <div className="flex-1 text-center">
            <p className="text-[10px] text-slate-500 mb-1">逐集拼凑方案</p>
            <p className={`text-sm font-bold ${recommendedPlan === "per_episode" ? "text-green-400" : "text-slate-400"}`}>
              {totalSizeEpisode} GB
            </p>
            <p className="text-[10px] text-slate-600">{foundCount} 集找到 / {missingCount} 集缺失</p>
          </div>
        </div>
      )}

      {/* 逐集表格 */}
      <div className="border border-white/[0.04] rounded-lg overflow-hidden">
        <div className="grid grid-cols-[60px_1fr_80px_60px_60px] gap-2 px-3 py-2 bg-white/[0.02] text-[10px] text-slate-500 font-medium">
          <span>集号</span><span>推荐资源</span><span>大小</span><span>做种</span><span>操作</span>
        </div>
        {episodes.map(({ ep, status, recommended, alternatives }) => (
          <div key={ep}>
            <div className={`grid grid-cols-[60px_1fr_80px_60px_60px] gap-2 px-3 py-2 text-xs border-t border-white/[0.02] ${
              status === "not_found" ? "bg-red-500/5" : ""
            }`}>
              <span className="text-slate-400 font-mono">E{String(ep).padStart(2, "0")}</span>
              {status === "found" && recommended ? (
                <>
                  <span className="text-slate-300 truncate" title={recommended.quality?.display}>
                    {recommended.quality?.display || recommended.quality_tag}
                  </span>
                  <span className="text-slate-400">{recommended.size_gb} GB</span>
                  <span className={recommended.seeders > 5 ? "text-green-500" : "text-yellow-500"}>{recommended.seeders}</span>
                  <button onClick={() => setExpandedEp(expandedEp === ep ? null : ep)}
                    className="text-[10px] text-blue-400 hover:text-blue-300">
                    {alternatives.length > 0 ? `${alternatives.length}个备选` : "—"}
                  </button>
                </>
              ) : (
                <span className="col-span-4 text-red-400 font-medium">⚠ 缺失</span>
              )}
            </div>
            {/* 备选展开 */}
            {expandedEp === ep && alternatives.length > 0 && (
              <div className="px-6 py-2 bg-white/[0.01] space-y-1">
                {alternatives.slice(0, 5).map((alt, ai) => (
                  <div key={ai} className="flex items-center gap-3 text-[10px]">
                    <span className="text-slate-500">{alt.quality?.display}</span>
                    <span className="text-slate-600">{alt.size_gb} GB</span>
                    <span className="text-slate-600">做种 {alt.seeders}</span>
                    <button onClick={() => { onSelectAlternative(ep, alt); setExpandedEp(null); }}
                      className="text-blue-400 hover:text-blue-300 ml-auto">选择</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── 折叠分组组件 ──
// ── 网盘筛选状态 ──
interface PanFilterState {
  panType: string;    // "" = 全部, "quark" / "aliyun" / "baidu" / "pan115" / "pikpak"
  source: string;     // "" = 全部, "pansearch" / "pansou" / "gogopanso" / "github"
  resolution: string; // "" = 全部, "2160p" / "1080p" / "720p"
  completeOnly: boolean; // 只看整季/全集
}

const DEFAULT_PAN_FILTERS: PanFilterState = {
  panType: "", source: "", resolution: "", completeOnly: false,
};

function applyPanFilters(results: PanResult[], filters: PanFilterState): PanResult[] {
  const isDefault = !filters.panType && !filters.source && !filters.resolution && !filters.completeOnly;
  if (isDefault) return results;
  return results.filter((r) => {
    if (filters.panType && r.pan_type !== filters.panType) return false;
    if (filters.source && r.source !== filters.source) return false;
    if (filters.resolution && r.resolution !== filters.resolution) return false;
    if (filters.completeOnly && !r.is_complete) return false;
    return true;
  });
}

// ── 网盘类型颜色和标签 ──
const PAN_TYPE_COLORS: Record<string, string> = {
  quark: "text-blue-400 bg-blue-400/10",
  aliyun: "text-orange-400 bg-orange-400/10",
  baidu: "text-green-400 bg-green-400/10",
  pan115: "text-purple-400 bg-purple-400/10",
  pikpak: "text-red-400 bg-red-400/10",
  unknown: "text-slate-400 bg-slate-400/10",
};
const PAN_TYPE_LABELS: Record<string, string> = {
  quark: "夸克", aliyun: "阿里", baidu: "百度",
  pan115: "115", pikpak: "PikPak", unknown: "未知",
};
const SOURCE_LABELS: Record<string, string> = {
  pansearch: "PanSearch", pansou: "PanSou", gogopanso: "狗狗盘搜",
  github: "GitHub仓库", rrdynb: "人人电影", ddys: "低端影视",
  sites: "通用站点", slowread: "慢读", wnsearch: "我能搜",
};

// ── 网盘筛选器栏（和 BT FilterBar 同级位置）──
function PanFilterBar({
  filters, onChange, groups, sourceStatuses,
}: {
  filters: PanFilterState;
  onChange: (f: PanFilterState) => void;
  groups: Record<string, PanResult[]>;
  sourceStatuses: PanSourceStatus[];
}) {
  // 从结果中动态提取可用选项
  const allResults = useMemo(() => {
    const all: PanResult[] = [];
    for (const items of Object.values(groups)) all.push(...items);
    return all;
  }, [groups]);

  const options = useMemo(() => {
    const panTypes = new Set<string>();
    const sources = new Set<string>();
    for (const r of allResults) {
      panTypes.add(r.pan_type);
      sources.add(r.source);
    }
    return { panTypes: Array.from(panTypes), sources: Array.from(sources) };
  }, [allResults]);

  const set = <K extends keyof PanFilterState>(key: K, val: PanFilterState[K]) =>
    onChange({ ...filters, [key]: val });
  const isFiltered = filters.panType || filters.source || filters.resolution || filters.completeOnly;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1 text-xs text-slate-400">
        网盘
        <select value={filters.panType} onChange={(e) => set("panType", e.target.value)}
          className="bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 outline-none focus:border-emerald-500/50 min-w-[90px]">
          <option value="">不限</option>
          {options.panTypes.map((pt) => (
            <option key={pt} value={pt}>{PAN_TYPE_LABELS[pt] || pt}</option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-slate-400">
        来源
        <select value={filters.source} onChange={(e) => set("source", e.target.value)}
          className="bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 outline-none focus:border-emerald-500/50 min-w-[90px]">
          <option value="">不限</option>
          {options.sources.map((s) => (
            <option key={s} value={s}>{SOURCE_LABELS[s] || s}</option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-slate-400">
        分辨率
        <select value={filters.resolution} onChange={(e) => set("resolution", e.target.value)}
          className="bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 outline-none focus:border-emerald-500/50 min-w-[90px]">
          <option value="">不限</option>
          <option value="2160p">4K</option>
          <option value="1080p">1080p</option>
          <option value="720p">720p</option>
        </select>
      </label>
      <label className="flex items-center gap-1.5 text-xs text-slate-400 pt-4 cursor-pointer">
        <input type="checkbox" checked={filters.completeOnly} onChange={(e) => set("completeOnly", e.target.checked)}
          className="w-3.5 h-3.5 rounded border-white/10 bg-white/[0.04] text-emerald-600 focus:ring-0" />
        仅整季
      </label>
      {isFiltered && (
        <button onClick={() => onChange(DEFAULT_PAN_FILTERS)}
          className="text-[10px] text-slate-500 hover:text-slate-300 pt-4 underline">清除</button>
      )}
      <div className="flex-1" />
      <div className="flex items-center gap-1.5 pt-4">
        {sourceStatuses.filter((s) => s.status !== "disabled").map((s) => (
          <span key={s.name} className={`text-[10px] px-1.5 py-0.5 rounded ${
            s.status === "success" ? "bg-green-500/10 text-green-400" :
            s.status === "failed" ? "bg-red-500/10 text-red-400" :
            "bg-white/[0.04] text-slate-600"
          }`}>
            {SOURCE_LABELS[s.name] || s.name} {s.status === "success" ? `✓${s.count}` : "✗"}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── 网盘搜索结果视图（纯展示，筛选器已提到外层）──
function PanResultsView({
  searching, groups, total, sourceStatuses, keyword, filters, onRetry, onTransfer,
}: {
  searching: boolean;
  groups: Record<string, PanResult[]>;
  total: number;
  sourceStatuses: PanSourceStatus[];
  keyword: string;
  filters: PanFilterState;
  onRetry: () => void;
  onTransfer: (r: PanResult) => void;
}) {
  // 展平 + 筛选 + 重新分组
  const allResults = useMemo(() => {
    const all: PanResult[] = [];
    for (const items of Object.values(groups)) all.push(...items);
    return all;
  }, [groups]);

  const filteredResults = useMemo(() => applyPanFilters(allResults, filters), [allResults, filters]);

  const filteredGroups = useMemo(() => {
    const g: Record<string, PanResult[]> = {};
    for (const r of filteredResults) {
      if (!g[r.pan_type]) g[r.pan_type] = [];
      g[r.pan_type].push(r);
    }
    const order = ["quark", "aliyun", "pan115", "pikpak", "baidu"];
    const ordered: Record<string, PanResult[]> = {};
    for (const pt of order) { if (g[pt]) ordered[pt] = g[pt]; }
    for (const pt of Object.keys(g)) { if (!ordered[pt]) ordered[pt] = g[pt]; }
    return ordered;
  }, [filteredResults]);

  const isFiltered = filters.panType || filters.source || filters.resolution || filters.completeOnly;

  if (searching) {
    return (
      <div className="flex flex-col items-center py-16">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500 mb-3" />
        <p className="text-[13px] text-slate-500">搜索网盘资源...</p>
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="text-center py-10">
        <p className="text-xs text-slate-600 mb-3">未搜到网盘资源</p>
        <button onClick={onRetry} className="text-xs text-emerald-400 hover:text-emerald-300">重试</button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[11px] text-slate-500">
          共 {filteredResults.length} 条{isFiltered ? `（筛选自 ${total} 条）` : ""}
        </p>
      </div>

      {Object.entries(filteredGroups).map(([panType, items]) => (
        <div key={panType} className="border border-white/[0.04] rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-2.5 bg-white/[0.02]">
            <span className={`text-[11px] px-2 py-0.5 rounded font-bold ${PAN_TYPE_COLORS[panType] || PAN_TYPE_COLORS.unknown}`}>
              {PAN_TYPE_LABELS[panType] || panType}
            </span>
            <span className="text-[10px] text-slate-500">{items.length} 条</span>
          </div>
          <div className="p-2 space-y-1.5">
            {items.map((r, i) => (
              <PanResultCard key={i} result={r} onTransfer={onTransfer} />
            ))}
          </div>
        </div>
      ))}

      {filteredResults.length === 0 && isFiltered && (
        <div className="text-center py-8">
          <p className="text-xs text-slate-600 mb-2">当前筛选条件无匹配结果</p>
        </div>
      )}
    </div>
  );
}

// ── 单条网盘结果卡片 ──
function PanResultCard({ result: r, onTransfer }: { result: PanResult; onTransfer: (r: PanResult) => void }) {
  const [copied, setCopied] = useState(false);
  const [transferring, setTransferring] = useState(false);

  const handleTransfer = async () => {
    if (r.pan_type === "quark") {
      // 夸克 → 调用后端自动转存
      setTransferring(true);
      onTransfer(r);
      setTransferring(false);
    } else {
      // 其他网盘 → 打开分享页 + 复制提取码
      if (r.password) {
        navigator.clipboard.writeText(r.password).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        }).catch(() => {});
      }
      window.open(r.share_url, "_blank");
    }
  };

  const btnLabel = r.pan_type === "quark"
    ? (transferring ? "转存中..." : "转存")
    : (r.password ? "打开(复制码)" : "打开");

  return (
    <div className="bg-[#0f0f0f] rounded-lg border border-white/[0.04] px-4 py-2.5 flex items-center gap-3 hover:border-white/[0.08] transition-colors">
      <div className="flex-1 min-w-0">
        <p className="text-[12px] text-slate-200 truncate" title={r.title}>
          {r.clean_title || r.title}
        </p>
        <div className="flex items-center gap-1.5 mt-1.5">
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${PAN_TYPE_COLORS[r.pan_type] || PAN_TYPE_COLORS.unknown}`}>
            {PAN_TYPE_LABELS[r.pan_type] || r.pan_type}
          </span>
          {r.resolution && r.resolution !== "unknown" && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
              r.resolution === "2160p" ? "bg-yellow-500/20 text-yellow-400" :
              r.resolution === "1080p" ? "bg-blue-500/15 text-blue-400" :
              "bg-white/[0.06] text-slate-500"
            }`}>{r.resolution}</span>
          )}
          {!r.is_complete && <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400">碎片</span>}
          <span className="text-[10px] text-slate-600">{r.source}</span>
          {r.password && (
            <span className="text-[10px] text-slate-500">
              码: {r.password} {copied && <span className="text-green-400">✓已复制</span>}
            </span>
          )}
        </div>
      </div>
      <div className="flex gap-1.5 flex-shrink-0">
        {r.pan_type === "quark" && (
          <button onClick={handleTransfer} disabled={transferring}
            className="px-3 py-1.5 rounded-lg text-[11px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition-colors disabled:opacity-50">
            {transferring ? "..." : "转存"}
          </button>
        )}
        <button onClick={() => {
          if (r.password) {
            navigator.clipboard.writeText(r.password).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            }).catch(() => {});
          }
          window.open(r.share_url, "_blank");
        }}
          className="px-3 py-1.5 rounded-lg text-[11px] font-bold bg-white/[0.06] text-slate-400 hover:text-white hover:bg-white/[0.10] transition-colors">
          打开
        </button>
      </div>
    </div>
  );
}
