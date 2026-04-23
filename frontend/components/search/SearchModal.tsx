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
import SourceTabs from "./SourceTabs";
import BtResultCard from "./BtResultCard";

type SearchTab = "bt" | "pan";

interface SourceTabState {
  keyword: string;
  results: EnhancedSearchResult[];
  searchedKeywords: string[];
  hitKeyword: string;
  searching: boolean;
}

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
  originalName?: string; // 原始语言名（日文/韩文/法语等）
  folderType?: string;   // "tv" | "season" | "movie" 等
  seasonNumber?: number;  // 季号
  episodeTag?: string;    // 如 "S01E01"
}

export default function SearchModal({
  open, query, onClose, defaultSavePath,
  currentResolution, qbConfigured = true, alistConfigured = false,
  shadowName, cleanName, mediaType,
  cnName, enName, originalName, folderType, seasonNumber, episodeTag,
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
  // AI 推荐
  const [aiRecommended, setAiRecommended] = useState<Map<number, string>>(new Map());
  const [aiRecommendEnabled, setAiRecommendEnabled] = useState(false); // AI 推荐开关（默认关，需用户主动开）
  const [aiAvailable, setAiAvailable] = useState(false); // AI 是否可用（后端配置了且 search_recommend 开启）
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

  // ── 源 Tab 切换状态 ──
  const [btActiveSource, setBtActiveSource] = useState("all");
  const [panActiveSource, setPanActiveSource] = useState("all");
  // 每个单源 Tab 的独立状态
  const [sourceTabStates, setSourceTabStates] = useState<Record<string, SourceTabState>>({});

  // 源→默认搜索词映射（前端侧，用于切换 Tab 时填入搜索框）
  const sourceDefaultKeywords = useMemo(() => {
    const cn = (cnName || "").trim();
    const en = (enName || "").trim();
    const sNum = seasonNumber || 0;
    const map: Record<string, string> = {};
    // 英文源
    for (const s of ["prowlarr", "bitsearch", "yts", "limetorrents"]) {
      let kw = en || cn || query;
      if (sNum > 0) kw += ` S${String(sNum).padStart(2, "0")}`;
      map[s] = kw;
    }
    // 中文源
    for (const s of ["cilixiong", "xl720", "acgrip", "bangumi_moe", "mikan"]) {
      let kw = cn || en || query;
      if (sNum > 0) kw += ` 第${sNum}季`;
      map[s] = kw;
    }
    // 动画源（Nyaa 优先原始语言名/英文）
    map["nyaa"] = originalName || en || cn || query;
    if (sNum > 0) map["nyaa"] += ` S${String(sNum).padStart(2, "0")}`;
    return map;
  }, [cnName, enName, originalName, query, seasonNumber]);

  // 源搜索词回显信息（从 SSE source_done 事件收集）
  const [sourceKeywordInfo, setSourceKeywordInfo] = useState<Record<string, { searched: string[]; hit: string }>>({});

  // 网盘源状态转为 Record 供 SourceTabs 使用
  const panSourceStatusMap = useMemo(() => {
    const m: Record<string, SourceStatus> = {};
    for (const s of panSourceStatuses) {
      m[s.name] = { status: s.status === "success" ? "done" : s.status === "failed" ? "failed" : "idle", count: s.count ?? 0 };
    }
    return m;
  }, [panSourceStatuses]);

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

  // 已知直搜源名称（用于区分 Prowlarr 索引器）
  const DIRECT_SOURCES = new Set(["bitsearch", "cilixiong", "xl720", "nyaa", "mikan", "yts", "limetorrents", "acgrip", "bangumi_moe"]);
  // Prowlarr 索引器（仅从 Prowlarr 来源的结果中提取，排除直搜源）
  const availableIndexers = useMemo(() => {
    const s = new Set<string>();
    results.forEach(r => {
      const src = (r as any)._source || r.indexer;
      // 只有 Prowlarr 来源的结果才提取索引器名
      if (src === "prowlarr" && r.indexer && !DIRECT_SOURCES.has(r.indexer)) {
        s.add(r.indexer);
      }
    });
    return Array.from(s);
  }, [results]);

  useEffect(() => { setKeyword(query); }, [query]);
  useEffect(() => {
    if (open && query) doSearch(query);
    if (open) {
      // 检查 AI 推荐是否可用
      api.getAIStatus().then(s => setAiAvailable(s.enabled && s.features?.search_recommend)).catch(() => setAiAvailable(false));
    }
    if (!open) {
      setResults([]); setError(""); setToast(null); setHitKeyword("");
      setFilters(DEFAULT_FILTERS); setDownloadingUrl(null);
      setSearchingStep(""); setSearching(false); setSavePath("");
      searchCache.current.clear(); userEditedRef.current = false;
      if (activeEsRef.current) { activeEsRef.current.close(); activeEsRef.current = null; }
      setPanResults([]); setPanGroups({}); setPanSourceStatuses([]); setPanTotal(0); setPanSearching(false);
      panCache.current.clear();
      setActiveTab("bt");
      setBtActiveSource("all"); setPanActiveSource("all"); setSourceTabStates({}); setSourceKeywordInfo({});
      setAiRecommended(new Map()); setAiRecommendEnabled(false);
    }
  }, [open, query]);

  const [searchingStep, setSearchingStep] = useState("");
  // 搜索源状态（SSE 实时更新）
  const [sourceStatuses, setSourceStatuses] = useState<Record<string, SourceStatus>>({});


  // 跟踪用户是否手动修改过搜索词
  const userEditedRef = useRef(false);
  // 跟踪当前 SSE 连接，新搜索开始时关闭旧的（防止结果混入）
  const activeEsRef = useRef<EventSource | null>(null);

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
    setHitKeyword(""); setSourceStatuses({}); setSourceKeywordInfo({});
    // 手动搜索时清除单源 tab 缓存（结果会被全量搜索覆盖）
    if (userEditedRef.current) {
      setSourceTabStates({});
    }

    try {
      setKeyword(q);
      setSearchingStep(`搜索：${q}`);

      // 用户手动输入的搜索词不传 cn_name/en_name，让后端用 query 自行分词
      // 点击标签或自动搜索时才传 cn_name/en_name 辅助后端选词
      const isUserEdited = userEditedRef.current;
      const sseUrl = api.searchStream(q, isUserEdited ? {} : { cn_name: cnName, en_name: enName, original_name: originalName, season_number: seasonNumber });
      // 关闭上一次未完成的 SSE 连接
      if (activeEsRef.current) {
        activeEsRef.current.close();
        activeEsRef.current = null;
      }
      const es = new EventSource(sseUrl);
      activeEsRef.current = es;
      let sseResults: EnhancedSearchResult[] = [];
      let sseDone = false;

      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => { es.close(); reject(new Error("timeout")); }, 90000);

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
              // 收集搜索词回显信息
              if (data.search_keywords || data.hit_keyword) {
                setSourceKeywordInfo(prev => ({
                  ...prev,
                  [data.source]: { searched: data.search_keywords || [], hit: data.hit_keyword || "" },
                }));
              }
              if (data.results && data.results.length > 0) {
                const newItems: EnhancedSearchResult[] = data.results.map((r: any) => ({
                  ...r,
                  _source: data.source,  // 标记来源（prowlarr / bitsearch / cilixiong 等）
                  quality: r.quality || { resolution: "", source: "", video_codec: "", audio_codec: "", has_chinese_sub: false, release_group: "", is_surround: false, display: r.quality_tag || "" },
                  quality_rank: r.quality_rank ?? 0,
                }));
                sseResults = [...sseResults, ...newItems];
                setResults([...sseResults]);
                setTotalRaw(sseResults.length);
                // 有结果后停止 loading spinner，让结果列表显示
                setSearching(false);
                setSearchingStep("");
              }
            } else if (data.type === "done") {
              sseDone = true;
              clearTimeout(timeout);
              es.close();
              activeEsRef.current = null;
              resolve();
            }
          } catch { /* 忽略解析错误 */ }
        };
        es.onerror = () => { clearTimeout(timeout); es.close(); activeEsRef.current = null; reject(new Error("sse_error")); };
      });

      if (sseDone && sseResults.length > 0) {
        searchCache.current.set(cacheKey, { results: sseResults, totalRaw: sseResults.length });
        // 异步 AI 推荐（仅用户开启时调用）
        setAiRecommended(new Map());
        if (aiRecommendEnabled) {
          api.aiSearchRecommend(q, sseResults.slice(0, 20), currentResolution ? { resolution: currentResolution } : undefined)
            .then(r => {
              if (r.recommended?.length) {
                const m = new Map<number, string>();
                r.recommended.forEach((item: any) => m.set(item.index, item.reason));
                setAiRecommended(m);
              }
            })
            .catch(() => {});
        }
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
  }, [cnName, enName, originalName, seasonNumber]);

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

  // ── 单源搜索（BT Tab 切换到具体源时使用）──
  const doSourceSearch = useCallback(async (source: string, kw: string) => {
    if (!kw.trim() || !source) return;
    // 更新该源 Tab 状态为搜索中
    setSourceTabStates(prev => ({
      ...prev,
      [source]: { keyword: kw, results: [], searchedKeywords: [], hitKeyword: "", searching: true },
    }));
    try {
      // 构造回退词（如果用户没手动改过词）
      const defaultKw = sourceDefaultKeywords[source] || "";
      const isUserEdited = kw !== defaultKw;
      const fallbacks = isUserEdited ? "" : (() => {
        // 从 cn/en 构造回退词列表
        const cn = (cnName || "").trim();
        const en = (enName || "").trim();
        const candidates = [cn, en, query].filter(Boolean);
        // 去掉和主搜索词相同的
        return candidates.filter(c => c.toLowerCase() !== kw.toLowerCase()).join(",");
      })();

      const d = await api.searchSource(source, kw, fallbacks || undefined);
      const items: EnhancedSearchResult[] = (d.results || []).map((r: any) => ({
        ...r,
        _source: source,
        quality: r.quality || { resolution: "", source: "", video_codec: "", audio_codec: "", has_chinese_sub: false, release_group: "", is_surround: false, display: r.quality_tag || "" },
        quality_rank: r.quality_rank ?? 0,
      }));
      setSourceTabStates(prev => ({
        ...prev,
        [source]: {
          keyword: kw,
          results: items,
          searchedKeywords: d.search_keywords || [kw],
          hitKeyword: d.hit_keyword || "",
          searching: false,
        },
      }));
      // 更新搜索词回显
      if (d.search_keywords || d.hit_keyword) {
        setSourceKeywordInfo(prev => ({
          ...prev,
          [source]: { searched: d.search_keywords || [], hit: d.hit_keyword || "" },
        }));
      }
    } catch {
      setSourceTabStates(prev => ({
        ...prev,
        [source]: { keyword: kw, results: [], searchedKeywords: [kw], hitKeyword: "", searching: false },
      }));
    }
  }, [cnName, enName, query, sourceDefaultKeywords]);

  // 切换源 Tab 时的处理
  // 保存"全部"模式下的搜索词，切回时恢复
  const allKeywordRef = useRef(query);

  const handleBtSourceSelect = useCallback((source: string) => {
    if (btActiveSource === "all") {
      // 离开"全部"Tab 前保存当前搜索词
      allKeywordRef.current = keyword;
    }
    setBtActiveSource(source);
    if (source === "all") {
      // 切回全部，恢复全局 keyword
      setKeyword(allKeywordRef.current);
      return;
    }
    // 切到单源：如果该源没有缓存状态，填入默认搜索词并自动搜索
    const existing = sourceTabStates[source];
    if (!existing || existing.results.length === 0) {
      const defaultKw = sourceDefaultKeywords[source] || keyword || query;
      setKeyword(defaultKw);
      doSourceSearch(source, defaultKw);
    } else {
      // 有缓存，恢复该源的搜索词
      setKeyword(existing.keyword);
    }
  }, [sourceTabStates, sourceDefaultKeywords, keyword, query, doSourceSearch]);

  // 网盘源 Tab 切换处理
  const panAllKeywordRef = useRef(query);
  const handlePanSourceSelect = useCallback((source: string) => {
    if (panActiveSource === "all") {
      panAllKeywordRef.current = keyword;
    }
    setPanActiveSource(source);
    if (source === "all") {
      setKeyword(panAllKeywordRef.current);
      return;
    }
    // 单源网盘：填入默认搜索词（中文优先）
    const cn = (cnName || "").trim();
    const en = (enName || "").trim();
    const defaultKw = cn || en || keyword || query;
    setKeyword(defaultKw);
    // TODO: 单源网盘搜索端点（当前网盘搜索是聚合的，暂时用全量搜索结果按源筛选）
  }, [panActiveSource, keyword, query, cnName, enName]);

  // 前端过滤：FilterBar 筛选 + 智能过滤（L2 匹配 + L3 软过滤）
  // 当前展示的结果：全部模式用 results，单源模式用该源的 results
  const activeResults = useMemo(() => {
    if (btActiveSource === "all") return results;
    return sourceTabStates[btActiveSource]?.results || [];
  }, [btActiveSource, results, sourceTabStates]);

  const displayResults = useMemo(() => {
    let list = activeResults;
    // 智能过滤开启时：排除后端标记的垃圾版本（枪版+低匹配度+死种）
    if (smartFilter) {
      list = list.filter(r => !(r as any).is_junk);
    }
    // 排序：有做种 > 无做种 > 磁力链接，同层内按 quality_score > match_score > seeders > size
    // 已知无做种数信息的源（seeders=0 但不是死种）——新增直搜源时在此注册
    const NO_SEEDER_INFO = new Set(["cilixiong", "xl720", "acgrip", "bangumi_moe"]);
    list = [...list].sort((a, b) => {
      // 三档分层：有做种/无做种数信息源(0) > 真正死种(1) > 磁力链接(2)
      const tier = (r: EnhancedSearchResult) => {
        if (r.seeders === 0 && r.size_gb === 0) return 2; // 磁力链接源
        if (r.seeders === 0) {
          // 无做种数信息的源不降权
          const src = (r as any)._source || "";
          if (NO_SEEDER_INFO.has(src)) return 0;
          return 1; // 真正的死种
        }
        return 0; // 有做种
      };
      const ta = tier(a), tb = tier(b);
      if (ta !== tb) return ta - tb;
      // quality_score 优先（质量分更直观）
      const sa = (a as any).quality_score ?? 0;
      const sb = (b as any).quality_score ?? 0;
      if (sb !== sa) return sb - sa;
      // match_score（后端 L2 计算）
      const aMatch = (a as any).match_score ?? 0;
      const bMatch = (b as any).match_score ?? 0;
      if (bMatch !== aMatch) return bMatch - aMatch;
      // seeders
      if (b.seeders !== a.seeders) return b.seeders - a.seeders;
      return b.size_gb - a.size_gb;
    });
    return list;
  }, [activeResults, smartFilter]);
  const filtered = applyFilters(displayResults, filters, disabledSources);

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
                <button key={ti} onClick={() => { userEditedRef.current = false; doSearch(tag.keyword); }}
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
              <SearchSettingsPanel open={showSettings} onClose={() => setShowSettings(false)} searching={searching} />
            </div>
          </div>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              {/* 搜索词回显标签（input 内部，回退链用箭头连接） */}
              <div className="flex items-center w-full bg-white/[0.04] border border-white/[0.06] rounded-lg overflow-hidden focus-within:border-blue-500/50">
                {activeTab === "bt" && Object.keys(sourceKeywordInfo).length > 0 && !searching && (
                  <div className="flex items-center gap-0.5 pl-2 flex-shrink-0">
                    <span className="text-[9px] text-slate-600 whitespace-nowrap mr-0.5">回退匹配:</span>
                    {(() => {
                      const allKws: string[] = [];
                      const hitKws = new Set<string>();
                      const seen = new Set<string>();
                      for (const info of Object.values(sourceKeywordInfo)) {
                        for (const kw of info.searched) {
                          if (!seen.has(kw)) { seen.add(kw); allKws.push(kw); }
                        }
                        if (info.hit) hitKws.add(info.hit);
                      }
                      // 排序：未命中的在前（回退过程），命中的在最后（最终停留）
                      const notHit = allKws.filter(kw => !hitKws.has(kw));
                      const hit = allKws.filter(kw => hitKws.has(kw));
                      const ordered = [...notHit, ...hit];
                      return ordered.map((kw, i) => (
                        <span key={i} className="flex items-center gap-0.5 flex-shrink-0">
                          {i > 0 && <span className="text-[9px] text-slate-700">→</span>}
                          <span className={`text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap ${
                            hitKws.has(kw) ? "bg-blue-500/15 text-blue-400" : "bg-white/[0.06] text-slate-600"
                          }`}>{kw}</span>
                        </span>
                      ));
                    })()}
                  </div>
                )}
                <input value={keyword} onChange={(e) => { setKeyword(e.target.value); userEditedRef.current = true; }}
                  onKeyDown={(e) => { if (e.key === "Enter") { activeTab === "bt" ? (btActiveSource === "all" ? doSearch(keyword) : doSourceSearch(btActiveSource, keyword)) : doPanSearch(keyword); } }}
                  placeholder="输入搜索关键词..."
                  className="flex-1 bg-transparent px-3 py-2 pr-[72px] text-sm text-white outline-none placeholder:text-slate-600 min-w-[120px]" />
                {/* 搜索框内右侧按钮组：AI 推荐 + 智能过滤 */}
                {activeTab === "bt" && (
                  <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-0.5">
                    {aiAvailable && (
                      <button onClick={() => setAiRecommendEnabled(!aiRecommendEnabled)}
                        title={aiRecommendEnabled ? "AI 推荐已开启：搜索完成后推荐最佳资源" : "AI 推荐已关闭"}
                        className={`w-7 h-7 rounded flex items-center justify-center text-[11px] font-bold transition-colors ${aiRecommendEnabled ? "text-blue-400 hover:bg-blue-600/20" : "text-slate-600 hover:text-slate-400"}`}>
                        🤖
                      </button>
                    )}
                    <button onClick={() => setSmartFilter(!smartFilter)}
                      title={smartFilter ? "智能过滤已开启：隐藏不相关/枪版/死种" : "智能过滤已关闭：显示全部结果"}
                      className={`w-7 h-7 rounded flex items-center justify-center text-sm transition-colors ${smartFilter ? "text-green-400 hover:bg-green-600/20" : "text-slate-600 hover:text-slate-400"}`}>
                      {smartFilter ? "🛡️" : "🔓"}
                    </button>
                  </div>
                )}
              </div>
            </div>
            <button onClick={() => { activeTab === "bt" ? (btActiveSource === "all" ? doSearch(keyword) : doSourceSearch(btActiveSource, keyword)) : doPanSearch(keyword); }} disabled={searching || panSearching || (btActiveSource !== "all" && sourceTabStates[btActiveSource]?.searching)}
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
          {/* 分割线：将 SourceTabs + 筛选器 和上面的搜索区域分开 */}
          <div className="border-t border-white/[0.04] pt-3 -mx-5 px-5 flex flex-col items-start gap-2">
          {activeTab === "bt" && (
            <SourceTabs
              type="bt"
              activeSource={btActiveSource}
              onSelect={handleBtSourceSelect}
              enabledSources={btSources.filter(s => s.enabled).map(s => s.name)}
              sourceStatuses={sourceStatuses}
              totalCount={results.length}
              allSearching={searching}
            />
          )}
          {activeTab === "bt" && (
            <FilterBar
              activeSource={btActiveSource}
              filters={filters}
              onChange={setFilters}
              onClear={() => setFilters(DEFAULT_FILTERS)}
              btSources={btSources}
              disabledSources={disabledSources}
              onToggleSource={toggleSource}
              availableIndexers={availableIndexers}
            />
          )}
          {activeTab === "pan" && (
            <SourceTabs
              type="pan"
              activeSource={panActiveSource}
              onSelect={handlePanSourceSelect}
              enabledSources={panSources.filter(s => s.enabled).map(s => s.name)}
              sourceStatuses={panSourceStatusMap}
              totalCount={panTotal}
              allSearching={panSearching}
            />
          )}
          {activeTab === "pan" && (
            <PanFilterBar activeSource={panActiveSource} filters={panFilters} onChange={setPanFilters} groups={panGroups} sourceStatuses={panSourceStatuses} panSources={panSources} disabledSources={disabledSources} onToggleSource={toggleSource} />
          )}
          </div>
        </div>

        {toast && (
          <div className={`mx-5 mt-3 px-4 py-2 rounded-lg text-xs ${toast.ok ? "bg-green-500/10 text-green-400 border border-green-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"}`}>{toast.msg}</div>
        )}

        {/* 结果列表 */}
        <div className="flex-1 overflow-y-auto p-5">
          {activeTab === "bt" ? (
            /* ── BT/磁力 Tab ── */
            <>
          {(btActiveSource === "all" ? searching : sourceTabStates[btActiveSource]?.searching) ? (
            <div className="flex flex-col items-center py-16">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mb-3" />
              <p className="text-[13px] text-slate-500 mb-3">
                {btActiveSource === "all"
                  ? (searchingStep || "搜罗全网资源...")
                  : `搜索 ${btActiveSource}...`}
              </p>
              {/* 各源实时状态（仅全部模式显示）*/}
              {btActiveSource === "all" && Object.keys(sourceStatuses).length > 0 && (
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
                    共 {activeResults.length} 条{smartFilter ? `，过滤后 ${displayResults.length} 条` : ""}{filtered.length !== displayResults.length ? `，筛选后 ${filtered.length} 条` : ""}
                    {/* 单源模式下显示搜索词回显 */}
                    {btActiveSource !== "all" && sourceKeywordInfo[btActiveSource]?.searched?.length > 0 && (
                      <span className="ml-2">
                        {sourceKeywordInfo[btActiveSource].searched.map((kw, i) => (
                          <span key={i} className={`inline-block text-[10px] px-1.5 py-0 rounded mr-1 ${
                            kw === sourceKeywordInfo[btActiveSource].hit ? "bg-blue-500/15 text-blue-400" : "bg-white/[0.04] text-slate-600"
                          }`}>{kw}</span>
                        ))}
                      </span>
                    )}
                  </p>
                </div>
              )}
              {/* 结果呈现 */}
              {filtered.map((res, i) => {
                // AI 推荐标记：从原始 results 数组中找到该结果的原始索引
                const origIdx = results.indexOf(res);
                const aiReason = origIdx >= 0 ? aiRecommended.get(origIdx) : undefined;
                return (
                  <BtResultCard key={i} res={res} index={i} currentResolution={curRes} qbConfigured={qbConfigured} downloadingUrl={downloadingUrl} onDownload={handleDownload} aiReason={aiReason} />
                );
              })}
              {filtered.length === 0 && activeResults.length > 0 && (
                <p className="text-center py-10 text-xs text-slate-600">无匹配筛选条件的结果</p>
              )}
              {activeResults.length === 0 && !searching && !(sourceTabStates[btActiveSource]?.searching) && !error && (
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
