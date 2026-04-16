// BT 搜索结果弹窗 — V2：结构化三行布局 + 分组模式 + 命中关键词标注
"use client";
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import type { EnhancedSearchResult, FilterState, PanResult, PanSourceStatus } from "@/types";
import { api } from "@/lib/api";
import FilterBar, { DEFAULT_FILTERS, applyFilters, INDEXER_TAG_STYLE, type SourceStatus } from "./FilterBar";
import EpisodeTable from "./EpisodeTable";
import PanFilterBar, { PanFilterState, DEFAULT_PAN_FILTERS } from "./PanFilterBar";
import PanResultsView from "./PanResultsView";
import SearchSettingsPanel from "./SearchSettingsPanel";

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
  const [savePath, setSavePath] = useState("");
  // savePath 为空时下载用 defaultSavePath
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
    } else if ((folderType === "tv" || folderType === "series") && sNum) {
      // tv/series 文件夹也支持季搜索
      if (cn) tags.push({ label: `${cn} 第${sNum}季`, keyword: `${cn} 第${sNum}季` });
      if (en && sTag && !isSame) tags.push({ label: `${en} ${sTag}`, keyword: `${en} ${sTag}` });
      if (cn) tags.push({ label: cn, keyword: cn });
      if (en && !isSame) tags.push({ label: en, keyword: en });
    } else if (episodeTag) {
      if (cn) tags.push({ label: `${cn} ${episodeTag}`, keyword: `${cn} ${episodeTag}` });
      if (en && !isSame) tags.push({ label: `${en} ${episodeTag}`, keyword: `${en} ${episodeTag}` });
      if (cn && en && !isSame) tags.push({ label: `${cn} ${en}`, keyword: `${cn} ${en}` });
      if (cn) tags.push({ label: cn, keyword: cn });
      if (en && !isSame) tags.push({ label: en, keyword: en });
    } else {
      // 默认场景：纯中文排最前（网盘搜索优先中文）
      if (cn) tags.push({ label: cn, keyword: cn });
      if (cn && en && !isSame) tags.push({ label: `${cn} ${en}`, keyword: `${cn} ${en}` });
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
  const [showSettings, setShowSettings] = useState(false);

  // ── 固定源列表（打开时加载一次）──
  const [btSources, setBtSources] = useState<{ name: string; label: string; enabled: boolean }[]>([]);
  const [panSources, setPanSources] = useState<{ name: string; label: string; enabled: boolean }[]>([]);
  const [disabledSources, setDisabledSources] = useState<Set<string>>(new Set());
  useEffect(() => {
    if (open) {
      api.getSearchSources().then((d: any) => {
        const sources = d.sources || [];
        setBtSources(sources.filter((s: any) => s.type === "bt"));
        setPanSources(sources.filter((s: any) => s.type === "pan"));
      }).catch(() => {});
    }
  }, [open]);
  const toggleSource = useCallback((name: string) => {
    setDisabledSources(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  }, []);

  // Prowlarr 索引器（从搜索结果动态提取）
  const availableIndexers = useMemo(() => {
    const s = new Set<string>();
    results.forEach(r => { if (r.indexer) s.add(r.indexer); });
    return Array.from(s);
  }, [results]);

  useEffect(() => { setKeyword(query); }, [query]);
  useEffect(() => {
    if (open && query) doSearch(query);
    if (!open) {
      setResults([]); setError(""); setToast(null); setHitKeyword("");
      setFilters(DEFAULT_FILTERS); setDownloadingUrl(null);
      setSearchingStep(""); setSearching(false); setSavePath("");
      searchCache.current.clear();
      setPanResults([]); setPanGroups({}); setPanSourceStatuses([]); setPanTotal(0); setPanSearching(false);
      panCache.current.clear();
      setActiveTab("bt");
    }
  }, [open, query]);

  const [searchingStep, setSearchingStep] = useState("");
  // 搜索源状态（SSE 实时更新）
  const [sourceStatuses, setSourceStatuses] = useState<Record<string, SourceStatus>>({});

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
    setHitKeyword(""); setSourceStatuses({});

    try {
      setKeyword(q);
      setSearchingStep(`搜索：${q}`);

      // 尝试 SSE 流式搜索
      const sseUrl = api.searchStream(q);
      const es = new EventSource(sseUrl);
      let sseResults: EnhancedSearchResult[] = [];
      let sseDone = false;

      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => { es.close(); reject(new Error("timeout")); }, 60000);

        es.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "status") {
              // 搜索中状态
              setSourceStatuses(prev => ({
                ...prev,
                [data.source]: { status: data.status as SourceStatus["status"], count: data.count ?? 0 },
              }));
              setSearchingStep(`${data.source}: 搜索中...`);
            } else if (data.type === "source_done") {
              // 单个源完成——立即追加结果
              setSourceStatuses(prev => ({
                ...prev,
                [data.source]: { status: (data.status === "done" ? "done" : "failed") as SourceStatus["status"], count: data.count ?? 0 },
              }));
              if (data.results && data.results.length > 0) {
                const newItems: EnhancedSearchResult[] = data.results.map((r: any) => ({
                  ...r,
                  quality: r.quality || { resolution: "", source: "", video_codec: "", audio_codec: "", has_chinese_sub: false, release_group: "", is_surround: false, display: r.quality_tag || "" },
                  quality_rank: r.quality_rank ?? 0,
                }));
                sseResults = [...sseResults, ...newItems];
                setResults([...sseResults]);
                setTotalRaw(sseResults.length);
              }
            } else if (data.type === "done") {
              sseDone = true;
              clearTimeout(timeout);
              es.close();
              resolve();
            }
          } catch { /* 忽略解析错误 */ }
        };
        es.onerror = () => { clearTimeout(timeout); es.close(); reject(new Error("sse_error")); };
      });

      if (sseDone && sseResults.length > 0) {
        searchCache.current.set(cacheKey, { results: sseResults, totalRaw: sseResults.length });
      }
      setResults(sseResults);
      setHitKeyword(q);
      setTotalRaw(sseResults.length);
    } catch {
      // SSE 失败，fallback 到普通搜索
      try {
        const d = await api.searchSingle(q, { skip_filter: true });
        const raw: EnhancedSearchResult[] = (d.bt_results || []).map((r: any) => ({
          ...r,
          quality: r.quality || { resolution: "", source: "", video_codec: "", audio_codec: "", has_chinese_sub: false, release_group: "", is_surround: false, display: r.quality_tag || "" },
          quality_rank: r.quality_rank ?? 0,
        }));
        if (raw.length > 0) {
          searchCache.current.set(q, { results: raw, totalRaw: d.total_raw || raw.length });
        }
        setResults(raw);
        setHitKeyword(q);
        setTotalRaw(d.total_raw || raw.length);
      } catch {
        setError("搜索失败，请检查 Prowlarr 配置后重试");
      }
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
    // 排序：匹配准确度 > quality_score > seeders > size_gb（全部降序）
    list = [...list].sort((a, b) => {
      const kw = keyword.toLowerCase();
      const aMatch = a.title.toLowerCase().includes(kw) ? 1 : 0;
      const bMatch = b.title.toLowerCase().includes(kw) ? 1 : 0;
      if (bMatch !== aMatch) return bMatch - aMatch;
      const sa = (a as any).quality_score ?? 0;
      const sb = (b as any).quality_score ?? 0;
      if (sb !== sa) return sb - sa;
      // 磁力链接源（seeders=0 且 size=0）视为有效资源，给基础分 1
      const aSeeders = (a.seeders === 0 && a.size_gb === 0) ? 1 : a.seeders;
      const bSeeders = (b.seeders === 0 && b.size_gb === 0) ? 1 : b.seeders;
      if (bSeeders !== aSeeders) return bSeeders - aSeeders;
      return b.size_gb - a.size_gb;
    });
    return list;
  }, [results, smartFilter, keyword]);
  const filtered = applyFilters(displayResults, filters, disabledSources);
  const isHigher = (res: EnhancedSearchResult) => {
    // 优先用 quality_score 比较（100 分制），回退到分辨率比较
    const resScore = (res as any).quality_score ?? 0;
    if (resScore > 0 && curRes) {
      const curScore = RES_RANK[curRes] ?? 0;
      // 粗略映射：2160p≈80, 1080p≈50, 720p≈25
      const curEstimate = curScore === 3 ? 80 : curScore === 2 ? 50 : curScore === 1 ? 25 : 0;
      return resScore > curEstimate + 5;
    }
    const rr = RES_RANK[res.quality?.resolution ?? ""] ?? 0;
    const cr = RES_RANK[curRes] ?? 0;
    return cr > 0 && rr > cr;
  };

  const handleDownload = async (res: EnhancedSearchResult, channel: "qb" | "alist") => {
    setDownloadingUrl(res.download_url); setToast(null);
    try {
      const d = await api.submitDownload({
        media_name: query, download_url: res.download_url,
        save_path: savePath || defaultSavePath, channel,
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
              {/* 索引器（直搜源品牌色）*/}
              <span className={`text-[10px] px-2 py-0.5 rounded ${INDEXER_TAG_STYLE[res.indexer] || "bg-white/[0.04] text-slate-500"}`}>{res.indexer}</span>
              {/* 中字高亮 */}
              {q?.has_chinese_sub && <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/15 text-blue-400 font-medium">中字</span>}
              {/* 整季包高亮 */}
              {seasonPack && <span className="text-[10px] px-2 py-0.5 rounded bg-yellow-500/15 text-yellow-400 font-medium">整季</span>}
              {/* 发布组 */}
              {q?.release_group && <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.04] text-slate-500">{q.release_group}</span>}
              {/* 质量评分 */}
              {(res as any).quality_score > 0 && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.04] text-slate-500 font-mono">{(res as any).quality_score}分</span>
              )}
            </div>
          </div>
          {/* 右侧：大小 + 做种 + 下载按钮并排 */}
          <div className="flex items-center gap-4 flex-shrink-0">
            <div className="text-right min-w-[65px]">
              <p className="text-[13px] font-bold text-slate-200">{res.size_gb > 0 ? `${res.size_gb} GB` : "—"}</p>
              <p className="text-[11px] text-slate-500">
                {res.seeders === 0 && res.size_gb === 0
                  ? <span className="text-slate-500">磁力</span>
                  : <>做种 <span className={res.seeders > 10 ? "text-green-400" : res.seeders > 0 ? "text-yellow-400" : "text-red-400"}>{res.seeders}</span></>
                }
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
      <div className="bg-[var(--background)] border border-white/[0.06] rounded-2xl w-full max-w-[1200px] max-h-[85vh] flex flex-col">
        {/* 顶栏 */}
        <div className="p-5 border-b border-white/[0.06] space-y-3 flex-shrink-0 overflow-visible relative z-10">
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
            <div className="flex items-center gap-1 relative">
              <button onClick={() => setShowSettings(!showSettings)}
                className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all ${showSettings ? "text-blue-400 bg-blue-500/10" : "text-slate-500 hover:text-white hover:bg-white/10"}`}
                title="搜索源设置">⚙️</button>
              <button onClick={onClose} className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">✕</button>
              <SearchSettingsPanel open={showSettings} onClose={() => setShowSettings(false)} />
            </div>
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
                placeholder={defaultSavePath ? `保存到：${defaultSavePath}` : "保存到：下载保存路径..."}
                className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-blue-500/50 font-mono transition-all group-hover:bg-white/[0.06]"
                title={savePath || defaultSavePath} />
            </div>
          </div>
          {activeTab === "bt" && (
            <div className="flex items-center gap-2 flex-wrap">
              <FilterBar 
                filters={filters} 
                onChange={setFilters} 
                onClear={() => setFilters(DEFAULT_FILTERS)} 
                btSources={btSources}
                sourceStatuses={sourceStatuses}
                disabledSources={disabledSources}
                onToggleSource={toggleSource}
                availableIndexers={availableIndexers}
              />
            </div>
          )}
          {activeTab === "pan" && (
            <PanFilterBar filters={panFilters} onChange={setPanFilters} groups={panGroups} sourceStatuses={panSourceStatuses} panSources={panSources} disabledSources={disabledSources} onToggleSource={toggleSource} />
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
              <p className="text-[13px] text-slate-500 mb-3">{searchingStep || "搜罗全网资源..."}</p>
              {/* 各源实时状态 */}
              {Object.keys(sourceStatuses).length > 0 && (
                <div className="flex flex-wrap gap-2 justify-center">
                  {Object.entries(sourceStatuses).map(([name, s]) => (
                    <span key={name} className={`text-[10px] px-2 py-0.5 rounded ${
                      s.status === "done" ? "bg-green-500/10 text-green-400" :
                      s.status === "failed" ? "bg-red-500/10 text-red-400" :
                      "bg-blue-500/10 text-blue-400 animate-pulse"
                    }`}>
                      {name} {s.status === "done" ? `✓ ${s.count}` : s.status === "failed" ? "✗" : "..."}
                    </span>
                  ))}
                </div>
              )}
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
              disabledSources={disabledSources}
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
