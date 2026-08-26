// 移动端路由与 query 参数的唯一来源。
//
// 调用点不许自己拼 URL：媒体路径里有反斜杠、空格、中文、# & ? 等字符，
// 手拼一定会在某个组合上翻车。构造和解析都走 URLSearchParams。

export const MOBILE_ROUTES = {
  discover: "/m",
  discoverDetail: "/m/discover/detail",
  library: "/m/library",
  libraryDetail: "/m/library/detail",
  /**
   * 底栏「搜索」= 找片子（豆瓣搜索），和发现页是一件事的两种入口。
   * 用户日常想的「搜索」是"这部片子有没有、评分多少"，不是"哪个种子画质好"。
   */
  search: "/m/search",
  /**
   * 资源搜索（BT / 磁力 / 网盘）**只从「搜索资源」「搜索升级」进入**，不进底栏 ——
   * 它需要先有一个明确的目标片子，凭空打开一个资源搜索框没有意义。
   */
  resource: "/m/resource",
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
  // ── 发现 ──
  title: "title",
  year: "year",
  /** 详情数据源：douban / tmdb / bangumi，来自榜单 tab 的 ratingSource */
  detailSource: "src",
  /** 条目在该源里的 id（豆瓣 id 或 bangumi subject id） */
  itemId: "id",
  /** 原始副标题，/media/info 用它辅助匹配 */
  subtitle: "sub",
  localStatus: "ls",
  localFolder: "lf",
  cover: "cover",
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

// ── 发现 ──

/**
 * 发现首页。tab 写进 URL 是为了"从哪进回哪里"：详情页返回时能落回原来的榜单，
 * 而不是一律弹回第一个 tab。切 tab 用 replace，不往历史栈里堆。
 */
export function discoverUrl(tab?: string): string {
  return buildUrl(MOBILE_ROUTES.discover, { [MOBILE_QUERY_KEYS.tab]: tab });
}

/** 从 query 里取发现榜单 tab；缺失时返回空串，由调用方决定默认 tab */
export function parseDiscoverTab(source: QuerySource): string {
  return readParam(source, MOBILE_QUERY_KEYS.tab);
}

/** 发现详情页能重建的全部状态。榜单条目不落盘，所以全部经 URL 传递 */
export interface MobileDiscoverDetailQuery {
  title: string;
  year?: string;
  /** movie / tv，来自条目自身或榜单 tab 的 mediaType */
  mediaType?: string;
  /** 详情数据源，对应榜单 tab 的 ratingSource */
  source?: string;
  /** 该源里的条目 id */
  id?: string;
  subtitle?: string;
  cnName?: string;
  enName?: string;
  originalName?: string;
  /** 榜单卡片上那张海报。带上它，详情页第一帧就有图，不用等 /media/info */
  cover?: string;
  /** 后端注入的本地状态，用于决定是否显示"查看本地" */
  localStatus?: string;
  /** 本地媒体库里的文件夹路径 */
  localFolder?: string;
  /** 来源榜单 tab，返回时用 */
  tab?: string;
}

export function discoverDetailUrl(query: MobileDiscoverDetailQuery): string {
  const K = MOBILE_QUERY_KEYS;
  return buildUrl(MOBILE_ROUTES.discoverDetail, {
    [K.title]: query.title,
    [K.year]: query.year,
    [K.mediaType]: query.mediaType,
    [K.detailSource]: query.source,
    [K.itemId]: query.id,
    [K.subtitle]: query.subtitle,
    [K.cnName]: query.cnName,
    [K.enName]: query.enName,
    [K.originalName]: query.originalName,
    [K.cover]: query.cover,
    // local_status 为 none 时不占 URL，解析端把缺失当 none
    [K.localStatus]: query.localStatus === "none" ? undefined : query.localStatus,
    [K.localFolder]: query.localFolder,
    [K.tab]: query.tab,
  });
}

export function parseDiscoverDetailQuery(source: QuerySource): MobileDiscoverDetailQuery {
  const K = MOBILE_QUERY_KEYS;
  return {
    title: readParam(source, K.title),
    year: readParam(source, K.year) || undefined,
    mediaType: readParam(source, K.mediaType) || undefined,
    source: readParam(source, K.detailSource) || undefined,
    id: readParam(source, K.itemId) || undefined,
    subtitle: readParam(source, K.subtitle) || undefined,
    cnName: readParam(source, K.cnName) || undefined,
    enName: readParam(source, K.enName) || undefined,
    originalName: readParam(source, K.originalName) || undefined,
    cover: readParam(source, K.cover) || undefined,
    localStatus: readParam(source, K.localStatus) || undefined,
    localFolder: readParam(source, K.localFolder) || undefined,
    tab: readParam(source, K.tab) || undefined,
  };
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

/** 底栏「搜索」：按片名找片子（豆瓣搜索），结果是发现卡片 */
export function discoverSearchUrl(q?: string): string {
  return buildUrl(MOBILE_ROUTES.search, { [MOBILE_QUERY_KEYS.query]: q });
}

/** 豆瓣搜索页的关键词 */
export function parseDiscoverSearchQuery(source: QuerySource): string {
  return readParam(source, MOBILE_QUERY_KEYS.query);
}

/** 资源搜索页可重建的全部状态 */
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

/** 资源搜索页（BT / 网盘）的 URL。名字带 resource 前缀，别和底栏的豆瓣搜索混起来 */
export function resourceSearchUrl(query: MobileSearchQuery): string {
  const K = MOBILE_QUERY_KEYS;
  return buildUrl(MOBILE_ROUTES.resource, {
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

export function parseResourceSearchQuery(source: QuerySource): MobileSearchQuery {
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
  // /m 是发现首页本身，/m/discover/* 是它的下钻页，都归发现 Tab
  if (pathname === MOBILE_ROUTES.discover) return "discover";
  if (pathname.startsWith("/m/discover")) return "discover";
  if (pathname.startsWith(MOBILE_ROUTES.library)) return "library";
  // 资源搜索没有自己的 Tab，归到「搜索」下面：它是从别处下钻进来的，
  // 底栏总得有一个高亮项，否则用户会觉得自己不在任何页面里
  if (pathname.startsWith(MOBILE_ROUTES.resource)) return "search";
  if (pathname.startsWith(MOBILE_ROUTES.search)) return "search";
  if (pathname.startsWith(MOBILE_ROUTES.downloads)) return "downloads";
  return null;
}

export function shouldShowBottomNav(pathname: string): boolean {
  return !ROUTES_WITHOUT_BOTTOM_NAV.some(route => pathname.startsWith(route));
}
