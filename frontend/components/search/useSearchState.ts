// 搜索弹窗状态管理 hook — 从 SearchModal.tsx 拆分
"use client";
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import type { EnhancedSearchResult, FilterState, PanResult, PanSourceStatus, ProviderCatalog, ProviderMetadata } from "@/types";
import { api } from "@/lib/api";
import { SEARCH_SSE_TIMEOUT_MS, AI_RECOMMEND_RESULT_LIMIT } from "@/lib/domain/search";
import { DEFAULT_FILTERS, applyFilters, type SourceStatus } from "./filterUtils";
import { useSearchLifecycle } from "./useSearchLifecycle";
import { type PanFilterState, DEFAULT_PAN_FILTERS } from "./panFilterUtils";

export type SearchTab = "bt" | "pan";

export interface SourceTabState {
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

export interface UseSearchStateParams {
  open: boolean;
  query: string;
  defaultSavePath: string;
  currentResolution?: string;
  mediaType?: string;
  cnName?: string;
  enName?: string;
  originalName?: string;
  folderType?: string;
  seasonNumber?: number;
  episodeTag?: string;
  qbConfigured?: boolean;
  /** 目标年份。只用于后端匹配加分，不拼进搜索词（拼进去会让 BT 站命中率骤降）。 */
  year?: string;
}

export function useSearchState({
  open, query, defaultSavePath, currentResolution, mediaType,
  cnName, enName, originalName, folderType, seasonNumber, episodeTag, year,
}: UseSearchStateParams) {
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<EnhancedSearchResult[]>([]);
  const [keyword, setKeyword] = useState(query);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{msg: string; ok: boolean} | null>(null);
  const [downloadingUrl, setDownloadingUrl] = useState<string | null>(null);
  const [hitKeyword, setHitKeyword] = useState("");
  const [smartFilter, setSmartFilter] = useState(false);  // 默认关闭过滤
  const [savePath, setSavePath] = useState("");
  // AI 推荐
  const [aiRecommended, setAiRecommended] = useState<Map<number, string>>(new Map());
  const [aiRecommendEnabled, setAiRecommendEnabled] = useState(false); // AI 推荐开关（默认关，需用户主动开）
  const [aiAvailable, setAiAvailable] = useState(false); // AI 是否可用（后端配置了且 search_recommend 开启）

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

  /** 取消时复位全部 loading 标志。
   *  被取消的请求走不到自己的收尾（收尾带代际门禁，否则会污染新请求的状态），
   *  所以这三个标志只能在取消动作里清。漏了它们，读 searching / panSearching 的
   *  按钮 disabled 会永久卡死，桌面只能关弹窗重开，路由页连这个时机都没有。 */
  const resetLoadingFlags = useCallback(() => {
    setSearching(false);
    setSearchingStep("");
    setPanSearching(false);
    setSourceTabStates(prev => {
      const stillSearching = Object.values(prev).some(state => state.searching);
      if (!stillSearching) return prev;
      const next: Record<string, SourceTabState> = {};
      for (const [name, state] of Object.entries(prev)) {
        next[name] = state.searching ? { ...state, searching: false } : state;
      }
      return next;
    });
  }, []);

  // 取消与代际门禁独立于 open 存在：路由搜索页没有"关闭弹窗"这个时机
  const {
    generationRef, activeEsRef, beginNewSearch, cancelCurrentSearch,
    setSseTimeout, clearSseTimeout, releaseEventSource, nextController,
  } = useSearchLifecycle(resetLoadingFlags);
  // ── 固定源列表（打开时加载一次）──
  const [btSources, setBtSources] = useState<SearchSourceView[]>([]);
  const [panSources, setPanSources] = useState<SearchSourceView[]>([]);
  const [disabledSources, setDisabledSources] = useState<Set<string>>(new Set());

  // 源→默认搜索词映射（从 provider capabilities 派生，用于切换 Tab 时填入搜索框）
  const sourceDefaultKeywords = useMemo(() => {
    const cn = (cnName || "").trim();
    const en = (enName || "").trim();
    const original = (originalName || "").trim();
    const sNum = seasonNumber || 0;
    const map: Record<string, string> = {};
    for (const source of btSources) {
      map[source.name] = buildDefaultKeyword(source.capabilities, { cn, en, original, query, seasonNumber: sNum });
    }
    return map;
  }, [btSources, cnName, enName, originalName, query, seasonNumber]);

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

  useEffect(() => {
    if (open) {
      api.getProviders()
        .then((catalog: ProviderCatalog) => {
          const availableSearch = catalog.search.filter(provider => provider.available !== false);
          const availablePan = catalog.panSearch.filter(provider => provider.available !== false);
          setBtSources(toSearchSources(availableSearch.filter(provider => provider.type === "bt")));
          setPanSources(toSearchSources(availablePan));
        })
        .catch(() => {
          api.getSearchSources().then((d: any) => {
            const sources = d.sources || [];
            setBtSources(sources.filter((s: any) => s.type === "bt").map(toLegacySearchSource));
            setPanSources(sources.filter((s: any) => s.type === "pan").map(toLegacySearchSource));
          }).catch(() => {});
        });
    }
  }, [open]);
  const toggleSource = useCallback((name: string) => {
    setDisabledSources(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  }, []);

  // Prowlarr 索引器（仅从 Prowlarr 来源的结果中提取，排除直搜源）
  const availableIndexers = useMemo(() => {
    const s = new Set<string>();
    const indexerProviderSources = new Set(btSources.filter(src => src.capabilities.includes("indexers")).map(src => src.name));
    const directSources = new Set(btSources.filter(src => !indexerProviderSources.has(src.name)).map(src => src.name));
    results.forEach(r => {
      const src = (r as any)._source || r.indexer;
      // 只有带 indexers 能力的聚合 provider 才提取索引器名
      if (indexerProviderSources.has(src) && r.indexer && !directSources.has(r.indexer)) {
        s.add(r.indexer);
      }
    });
    return Array.from(s);
  }, [results, btSources]);

  const indexerProviderSources = useMemo(() => new Set(
    btSources.filter(source => source.capabilities.includes("indexers")).map(source => source.name)
  ), [btSources]);

  const noSeederInfoSources = useMemo(() => new Set(
    btSources.filter(source => !source.capabilities.includes("seeders")).map(source => source.name)
  ), [btSources]);

  // query 或媒体上下文变化 = 换了要搜的东西，之前"用户手改过词"的判断随之失效，
  // 否则来自媒体详情的结构化搜索会被上一轮的手动输入状态污染。
  useEffect(() => {
    setKeyword(query);
    userEditedRef.current = false;
    allKeywordRef.current = query;
    panAllKeywordRef.current = query;
  }, [query, cnName, enName, originalName, folderType, seasonNumber]);

  /** 清掉一次搜索产生的全部结果态（换词、清空搜索词都走这里）。不动缓存和用户选择。 */
  const resetSearchResults = useCallback(() => {
    setResults([]); setError(""); setToast(null); setHitKeyword("");
    setSearching(false); setSearchingStep("");
    setSourceStatuses({}); setSourceKeywordInfo({}); setSourceTabStates({});
    setPanResults([]); setPanGroups({}); setPanSourceStatuses([]); setPanTotal(0); setPanSearching(false);
    setAiRecommended(new Map());
    userEditedRef.current = false;
  }, []);

  useEffect(() => {
    if (open && query) doSearch(query);
    // 搜索词被清空：取消在途请求并清干净，不留上一次的结果和错误
    if (open && !query) { cancelCurrentSearch(); resetSearchResults(); }
    if (open) {
      // 检查 AI 推荐是否可用
      api.getAIStatus().then(s => setAiAvailable(s.enabled && s.features?.search_recommend)).catch(() => setAiAvailable(false));
    }
    if (!open) {
      cancelCurrentSearch();
      resetSearchResults();
      setFilters(DEFAULT_FILTERS); setDownloadingUrl(null); setSavePath("");
      searchCache.current.clear();
      panCache.current.clear();
      setActiveTab("bt");
      setBtActiveSource("all"); setPanActiveSource("all");
      setAiRecommendEnabled(false);
    }
  }, [open, query]);

  const [searchingStep, setSearchingStep] = useState("");
  // 搜索源状态（SSE 实时更新）
  const [sourceStatuses, setSourceStatuses] = useState<Record<string, SourceStatus>>({});

  // 跟踪用户是否手动修改过搜索词
  const userEditedRef = useRef(false);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) return;

    // 先取消旧搜索再看缓存：否则上一次未完成的流会在缓存结果显示后把它覆盖掉
    const thisSearchId = beginNewSearch();

    // 检查缓存
    const cacheKey = q;
    const cached = searchCache.current.get(cacheKey);
    if (cached) {
      setResults(cached.results);
      setHitKeyword(q);
      setKeyword(q);
      setSearching(false);
      setSearchingStep("");
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
      // year 两种情况都传：它不参与选词，只让后端给同年的结果加分。
      // 用户手改搜索词后年份依然是同一部片的年份，没有理由丢掉。
      const sseUrl = api.searchStream(q, isUserEdited
        ? { year }
        : { cn_name: cnName, en_name: enName, original_name: originalName, season_number: seasonNumber, year });
      const es = new EventSource(sseUrl);
      activeEsRef.current = es;
      let sseResults: EnhancedSearchResult[] = [];
      let sseDone = false;
      // 后端在"无可用搜索源"时会在 done 事件里带 error/message，必须呈现给用户
      let sseErrorMessage = "";

      await new Promise<void>((resolve, reject) => {
        setSseTimeout(() => { es.close(); reject(new Error("timeout")); }, SEARCH_SSE_TIMEOUT_MS);

        es.onmessage = (event) => {
          // 代际不匹配 → 旧搜索的残留消息，丢弃。
          // 置空 ref 必须带条件，否则会抹掉新搜索刚写进去的连接。
          // 必须 resolve：光 return 会让这个 Promise 永不 settle，
          // 后面的 await 永久挂起，连闭包里的结果数组一起留在内存里。
          if (generationRef.current !== thisSearchId) {
            es.close();
            releaseEventSource(es, thisSearchId);
            clearSseTimeout();
            resolve();
            return;
          }
          try {
            const data = JSON.parse(event.data);
            if (data.type === "status") {
              if (generationRef.current !== thisSearchId) return;
              setSourceStatuses(prev => ({
                ...prev,
                [data.source]: { status: data.status as SourceStatus["status"], count: data.count ?? 0 },
              }));
              setSearchingStep(`${data.source}: 搜索中...`);
            } else if (data.type === "source_done") {
              if (generationRef.current !== thisSearchId) return;
              setSourceStatuses(prev => ({
                ...prev,
                [data.source]: { status: (data.status === "done" ? "done" : "failed") as SourceStatus["status"], count: data.count ?? 0 },
              }));
              if (data.search_keywords || data.hit_keyword) {
                setSourceKeywordInfo(prev => ({
                  ...prev,
                  [data.source]: { searched: data.search_keywords || [], hit: data.hit_keyword || "" },
                }));
              }
              if (data.results && data.results.length > 0) {
                const newItems: EnhancedSearchResult[] = data.results.map((r: any) => ({
                  ...r,
                  _source: data.source,
                  quality: r.quality || { resolution: "", source: "", video_codec: "", audio_codec: "", has_chinese_sub: false, release_group: "", is_surround: false, display: r.quality_tag || "" },
                  quality_rank: r.quality_rank ?? 0,
                }));
                sseResults = [...sseResults, ...newItems];
                if (generationRef.current === thisSearchId) {
                  setResults([...sseResults]);
                  setSearching(false);
                  setSearchingStep("");
                }
              }
            } else if (data.type === "done") {
              sseDone = true;
              if (data.error) {
                sseErrorMessage = data.message || "没有可用的搜索源";
              }
              clearSseTimeout();
              es.close();
              releaseEventSource(es, thisSearchId);
              resolve();
            }
          } catch { /* 忽略解析错误 */ }
        };
        es.onerror = () => {
          clearSseTimeout();
          es.close();
          releaseEventSource(es, thisSearchId);
          reject(new Error("sse_error"));
        };
      });

      if (sseDone && sseResults.length > 0) {
        searchCache.current.set(cacheKey, { results: sseResults, totalRaw: sseResults.length });
        // 异步 AI 推荐（仅用户开启时调用）
        if (generationRef.current === thisSearchId) {
          setAiRecommended(new Map());
          if (aiRecommendEnabled) {
            const aiController = nextController("bt");
            api.aiSearchRecommend(q, sseResults.slice(0, AI_RECOMMEND_RESULT_LIMIT), currentResolution ? { resolution: currentResolution } : undefined, aiController.signal)
              .then(r => {
                if (generationRef.current !== thisSearchId) return;
                if (r.recommended?.length) {
                  const m = new Map<number, string>();
                  r.recommended.forEach((item: any) => m.set(item.index, item.reason));
                  setAiRecommended(m);
                }
              })
              .catch(() => {});
          }
        }
      }
      if (generationRef.current === thisSearchId) {
        setResults(sseResults);
        setHitKeyword(q);
        // 后端明确报了"无可用源"：直接显示原因，不要走静默的空结果
        if (sseErrorMessage && sseResults.length === 0) {
          setError(sseErrorMessage);
        }
      }
    } catch (e: any) {
      // SSE 失败，fallback 到普通搜索（仅当前搜索仍有效时）
      if (generationRef.current !== thisSearchId) return;
      try {
        const fallbackController = nextController("bt");
        const d = await api.searchSingle(q, { skip_filter: true, year }, fallbackController.signal);
        const raw: EnhancedSearchResult[] = (d.bt_results || []).map((r: any) => ({
          ...r,
          quality: r.quality || { resolution: "", source: "", video_codec: "", audio_codec: "", has_chinese_sub: false, release_group: "", is_surround: false, display: r.quality_tag || "" },
          quality_rank: r.quality_rank ?? 0,
        }));
        if (raw.length > 0) {
          searchCache.current.set(q, { results: raw, totalRaw: d.total_raw || raw.length });
        }
        if (generationRef.current === thisSearchId) {
          setResults(raw);
          setHitKeyword(q);
        }
      } catch (e: any) {
        if (generationRef.current === thisSearchId) {
          const msg = e?.message || "";
          if (msg.includes("timeout") || msg.includes("超时")) {
            setError("搜索超时，请检查网络连接或代理配置");
          } else if (msg.includes("proxy") || msg.includes("ECONNREFUSED")) {
            setError("网络连接失败，请检查代理配置是否正确");
          } else if (msg.includes("429") || msg.includes("限频")) {
            setError("请求过于频繁，请稍后重试");
          } else {
            setError("搜索失败，请检查搜索源配置后重试");
          }
        }
      }
    }
    if (generationRef.current === thisSearchId) {
      setSearching(false);
      setSearchingStep("");
    }
  }, [cnName, enName, originalName, seasonNumber, aiRecommendEnabled, currentResolution,
      beginNewSearch, generationRef, activeEsRef, setSseTimeout, clearSseTimeout, releaseEventSource, nextController]);

  // ── 网盘搜索 ──
  // 网盘与单源搜索原先完全没有代际门禁：连续切换时先发起的响应回得晚就会盖掉后发起的。
  // 这里不递增代际（切 Tab 属于同一次搜索），只按当前代际做门禁，并 abort 本通道的旧请求。
  const doPanSearch = useCallback(async (q: string) => {
    if (!q.trim()) return;
    const gen = generationRef.current;
    const controller = nextController("pan");
    const stale = () => generationRef.current !== gen || controller.signal.aborted;

    const cached = panCache.current.get(q);
    if (cached) {
      setPanResults(cached.results); setPanGroups(cached.groups);
      setPanSourceStatuses(cached.statuses); setPanTotal(cached.total);
      setPanSearching(false);
      return;
    }
    setPanSearching(true); setPanResults([]); setPanGroups({}); setError("");
    try {
      const d = await api.searchPan(q, mediaType, controller.signal);
      if (stale()) return;
      const results: PanResult[] = d.results || [];
      const groups: Record<string, PanResult[]> = d.groups || {};
      const statuses: PanSourceStatus[] = d.source_statuses || [];
      const total = d.total || 0;
      setPanResults(results); setPanGroups(groups);
      setPanSourceStatuses(statuses); setPanTotal(total);
      if (results.length > 0) {
        panCache.current.set(q, { results, groups, statuses, total });
      } else {
        // 0 结果时区分"没搜到"和"没有可用源"，后者必须给出原因
        const disabled = statuses.find(s => s.status === "disabled" && s.error);
        const failed = statuses.find(s => s.status === "failed" && s.error);
        const msg = d.message || disabled?.error || failed?.error || "";
        if (msg) setError(msg);
      }
    } catch (e: any) {
      // 被取消不是失败，不该弹错误
      if (stale()) return;
      setPanResults([]);
      setError(e?.message ? `网盘搜索失败：${e.message}` : "网盘搜索失败，请检查网络或网盘搜索源配置");
    }
    if (stale()) return;
    setPanSearching(false);
  }, [mediaType, generationRef, nextController]);

  // ── 单源搜索（BT Tab 切换到具体源时使用）──
  const doSourceSearch = useCallback(async (source: string, kw: string) => {
    if (!kw.trim() || !source) return;
    const gen = generationRef.current;
    const controller = nextController("source");
    const stale = () => generationRef.current !== gen || controller.signal.aborted;
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
        const cn = (cnName || "").trim();
        const en = (enName || "").trim();
        const candidates = [cn, en, query].filter(Boolean);
        return candidates.filter(c => c.toLowerCase() !== kw.toLowerCase()).join(",");
      })();

      const d = await api.searchSource(source, kw, fallbacks || undefined, controller.signal);
      if (stale()) return;
      if (d.error) {
        setError(d.error);
        setSourceTabStates(prev => ({
          ...prev,
          [source]: { keyword: kw, results: [], searchedKeywords: [kw], hitKeyword: "", searching: false },
        }));
        return;
      }
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
      if (d.search_keywords || d.hit_keyword) {
        setSourceKeywordInfo(prev => ({
          ...prev,
          [source]: { searched: d.search_keywords || [], hit: d.hit_keyword || "" },
        }));
      }
    } catch {
      // 被取消不算失败，不该把该源 Tab 写成空结果
      if (stale()) return;
      setSourceTabStates(prev => ({
        ...prev,
        [source]: { keyword: kw, results: [], searchedKeywords: [kw], hitKeyword: "", searching: false },
      }));
    }
  }, [cnName, enName, query, sourceDefaultKeywords, generationRef, nextController]);

  // 切换源 Tab 时的处理
  // 保存"全部"模式下的搜索词，切回时恢复
  const allKeywordRef = useRef(query);

  const handleBtSourceSelect = useCallback((source: string) => {
    if (btActiveSource === "all") {
      allKeywordRef.current = keyword;
    }
    setBtActiveSource(source);
    if (source === "all") {
      setKeyword(allKeywordRef.current);
      return;
    }
    // 切到单源：优先从 SSE 全量结果中提取该源的结果
    const existing = sourceTabStates[source];
    if (existing && existing.results.length > 0) {
      setKeyword(existing.keyword);
      return;
    }
    // 从 SSE 全量结果中过滤该源的结果
    const sseSourceResults = results.filter((r: any) => r._source === source);
    if (sseSourceResults.length > 0) {
      const sseKw = sourceKeywordInfo[source]?.hit || keyword || query;
      setKeyword(sseKw);
      setSourceTabStates(prev => ({
        ...prev,
        [source]: {
          keyword: sseKw,
          results: sseSourceResults,
          searchedKeywords: sourceKeywordInfo[source]?.searched || [sseKw],
          hitKeyword: sourceKeywordInfo[source]?.hit || "",
          searching: false,
        },
      }));
      return;
    }
    // SSE 中也没有该源的结果，触发单源搜索
    const defaultKw = sourceDefaultKeywords[source] || keyword || query;
    setKeyword(defaultKw);
    doSourceSearch(source, defaultKw);
  }, [sourceTabStates, sourceDefaultKeywords, keyword, query, doSourceSearch, results, sourceKeywordInfo]);

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
    list = [...list].sort((a, b) => {
      const tier = (r: EnhancedSearchResult) => {
        if (r.seeders === 0 && r.size_gb === 0) return 2;
        if (r.seeders === 0) {
          const src = (r as any)._source || "";
          if (noSeederInfoSources.has(src)) return 0;
          return 1;
        }
        return 0;
      };
      const ta = tier(a), tb = tier(b);
      if (ta !== tb) return ta - tb;
      const sa = (a as any).quality_score ?? 0;
      const sb = (b as any).quality_score ?? 0;
      if (sb !== sa) return sb - sa;
      const aMatch = (a as any).match_score ?? 0;
      const bMatch = (b as any).match_score ?? 0;
      if (bMatch !== aMatch) return bMatch - aMatch;
      if (b.seeders !== a.seeders) return b.seeders - a.seeders;
      return b.size_gb - a.size_gb;
    });
    return list;
  }, [activeResults, smartFilter, noSeederInfoSources]);
  const filtered = applyFilters(displayResults, filters, disabledSources, noSeederInfoSources, indexerProviderSources);

  const handleDownload = async (res: EnhancedSearchResult, channel: "qb" | "alist") => {
    setDownloadingUrl(res.download_url); setToast(null);
    try {
      const d = await api.submitDownload({
        media_name: query, download_url: res.download_url,
        save_path: savePath || defaultSavePath, channel,
      });
      if (d.success) { setToast({ msg: "任务已提交到下载队列", ok: true }); }
      else { setToast({ msg: "失败: " + (d.error || d.task?.error || "未知错误"), ok: false }); }
    } catch { setToast({ msg: "通信失败，请检查网络", ok: false }); }
    finally { setDownloadingUrl(null); }
  };

  return {
    // 搜索状态
    searching, results, keyword, setKeyword, filters, setFilters,
    error, toast, setToast, downloadingUrl, hitKeyword,
    smartFilter, setSmartFilter, savePath, setSavePath,
    // AI
    aiRecommended, aiRecommendEnabled, setAiRecommendEnabled, aiAvailable,
    // 标签
    searchTags, curRes,
    // Tab
    activeTab, setActiveTab,
    // 网盘
    panResults, panGroups, panSourceStatuses, panSearching, panTotal, panFilters, setPanFilters,
    // 设置
    showSettings, setShowSettings,
    // 源 Tab
    btActiveSource, panActiveSource,
    sourceTabStates, sourceKeywordInfo,
    panSourceStatusMap,
    // 源列表
    btSources, panSources, disabledSources, toggleSource,
    noSeederInfoSources,
    indexerProviderSources,
    availableIndexers,
    // 搜索步骤
    searchingStep, sourceStatuses,
    // ref
    userEditedRef,
    // 搜索函数
    doSearch, doPanSearch, doSourceSearch,
    // 生命周期：路由页离开、切后台时由调用方主动取消
    cancelCurrentSearch, resetSearchResults,
    handleBtSourceSelect, handlePanSourceSelect,
    handleDownload,
    // 计算结果
    activeResults, displayResults, filtered,
  };
}

interface SearchSourceView {
  name: string;
  label: string;
  enabled: boolean;
  capabilities: string[];
}

function toSearchSources(providers: ProviderMetadata[]) {
  return providers.map(provider => ({
    name: provider.id,
    label: provider.name,
    enabled: provider.enabled,
    capabilities: provider.capabilities,
  }));
}

function toLegacySearchSource(source: { name: string; label: string; enabled: boolean }) {
  return {
    name: source.name,
    label: source.label,
    enabled: source.enabled,
    capabilities: ["search", "magnet", "torrent", "size", "seeders"],
  };
}

function buildDefaultKeyword(
  capabilities: string[],
  values: { cn: string; en: string; original: string; query: string; seasonNumber: number },
) {
  const priority = capabilities
    .filter(capability => capability.startsWith("keyword_"))
    .map(capability => capability.replace("keyword_", ""));
  const langs = priority.length > 0 ? priority : ["en", "cn", "query"];
  const keyword = langs
    .map(lang => {
      if (lang === "cn") return values.cn;
      if (lang === "en") return values.en;
      if (lang === "original") return values.original;
      return values.query;
    })
    .find(Boolean) || values.query;

  if (!keyword || values.seasonNumber <= 0) return keyword;
  if (capabilities.includes("season_cn")) return `${keyword} 第${values.seasonNumber}季`;
  return `${keyword} S${String(values.seasonNumber).padStart(2, "0")}`;
}
