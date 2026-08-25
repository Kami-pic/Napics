// 移动端路由与 query 参数的唯一来源。
//
// 调用点不许自己拼 URL：媒体路径里有反斜杠、空格、中文、# & ? 等字符，
// 手拼一定会在某个组合上翻车。构造和解析都走 URLSearchParams。

export const MOBILE_ROUTES = {
  discover: "/m",
  library: "/m/library",
  libraryDetail: "/m/library/detail",
  search: "/m/search",
  downloads: "/m/downloads",
  play: "/m/play",
} as const;

export type MobileRoute = (typeof MOBILE_ROUTES)[keyof typeof MOBILE_ROUTES];

/** query 参数名集中在此，组件里不写字符串字面量 */
export const MOBILE_QUERY_KEYS = {
  path: "path",
  query: "q",
  tab: "tab",
  cnName: "cn",
  enName: "en",
  originalName: "original",
  mediaType: "mtype",
  folderType: "ftype",
  season: "season",
  resolution: "res",
  savePath: "save",
} as const;

export type MobileSearchTab = "bt" | "pan";

/** 底部主 Tab。用 replace 导航，避免返回键在 Tab 之间来回循环 */
export const MOBILE_NAV_ITEMS = [
  { key: "library", label: "媒体库", route: MOBILE_ROUTES.library },
  { key: "discover", label: "发现", route: MOBILE_ROUTES.discover },
  { key: "search", label: "搜索", route: MOBILE_ROUTES.search },
  { key: "downloads", label: "下载", route: MOBILE_ROUTES.downloads },
] as const;

export type MobileNavKey = (typeof MOBILE_NAV_ITEMS)[number]["key"];

/** 播放页隐藏底栏，所以它不在导航表里 */
export const ROUTES_WITHOUT_BOTTOM_NAV: readonly string[] = [MOBILE_ROUTES.play];

/**
 * Server Component 拿到的 searchParams 与客户端的 URLSearchParams 形状不同，
 * 解析函数统一吃这个联合类型。
 */
export type QuerySource =
  | URLSearchParams
  | Record<string, string | string[] | undefined>;

function readParam(source: QuerySource, key: string): string {
  if (source instanceof URLSearchParams) return source.get(key) ?? "";
  const raw = source[key];
  if (Array.isArray(raw)) return raw[0] ?? "";
  return raw ?? "";
}

function buildUrl(route: string, params: Record<string, string | number | undefined>): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "" || value === 0) continue;
    sp.set(key, String(value));
  }
  const qs = sp.toString();
  return qs ? `${route}?${qs}` : route;
}

// ── 媒体库 ──

/** 媒体库列表页；path 为空时是库根 */
export function libraryUrl(path?: string): string {
  return buildUrl(MOBILE_ROUTES.library, { [MOBILE_QUERY_KEYS.path]: path });
}

/** 单个视频/剧集的详情页 */
export function libraryDetailUrl(path: string): string {
  return buildUrl(MOBILE_ROUTES.libraryDetail, { [MOBILE_QUERY_KEYS.path]: path });
}

/** 原生播放页 */
export function playUrl(path: string): string {
  return buildUrl(MOBILE_ROUTES.play, { [MOBILE_QUERY_KEYS.path]: path });
}

/** 从 query 里取出媒体路径 */
export function parsePathParam(source: QuerySource): string {
  return readParam(source, MOBILE_QUERY_KEYS.path);
}

// ── 搜索 ──

/** 搜索页可重建的全部状态 */
export interface MobileSearchQuery {
  q: string;
  tab: MobileSearchTab;
  cnName?: string;
  enName?: string;
  originalName?: string;
  mediaType?: string;
  folderType?: string;
  /** 季号；0 或缺失表示不带季 */
  season?: number;
  /** 当前已有的分辨率，用于洗版对比 */
  resolution?: string;
  /** 默认保存目录 */
  savePath?: string;
}

export function searchUrl(query: MobileSearchQuery): string {
  const K = MOBILE_QUERY_KEYS;
  return buildUrl(MOBILE_ROUTES.search, {
    [K.query]: query.q,
    // bt 是默认值，不写进 URL，省得每个链接都拖一截
    [K.tab]: query.tab === "pan" ? "pan" : undefined,
    [K.cnName]: query.cnName,
    [K.enName]: query.enName,
    [K.originalName]: query.originalName,
    [K.mediaType]: query.mediaType,
    [K.folderType]: query.folderType,
    [K.season]: query.season,
    [K.resolution]: query.resolution,
    [K.savePath]: query.savePath,
  });
}

export function parseSearchQuery(source: QuerySource): MobileSearchQuery {
  const K = MOBILE_QUERY_KEYS;
  const seasonRaw = readParam(source, K.season);
  const season = Number.parseInt(seasonRaw, 10);
  return {
    q: readParam(source, K.query),
    tab: readParam(source, K.tab) === "pan" ? "pan" : "bt",
    cnName: readParam(source, K.cnName) || undefined,
    enName: readParam(source, K.enName) || undefined,
    originalName: readParam(source, K.originalName) || undefined,
    mediaType: readParam(source, K.mediaType) || undefined,
    folderType: readParam(source, K.folderType) || undefined,
    season: Number.isFinite(season) && season > 0 ? season : undefined,
    resolution: readParam(source, K.resolution) || undefined,
    savePath: readParam(source, K.savePath) || undefined,
  };
}

// ── 导航状态 ──

/** 当前 pathname 对应哪个底部 Tab；下钻页归属它所属的 Tab */
export function activeNavKey(pathname: string): MobileNavKey | null {
  if (pathname === MOBILE_ROUTES.discover) return "discover";
  if (pathname.startsWith(MOBILE_ROUTES.library)) return "library";
  if (pathname.startsWith(MOBILE_ROUTES.search)) return "search";
  if (pathname.startsWith(MOBILE_ROUTES.downloads)) return "downloads";
  return null;
}

export function shouldShowBottomNav(pathname: string): boolean {
  return !ROUTES_WITHOUT_BOTTOM_NAV.some(route => pathname.startsWith(route));
}
