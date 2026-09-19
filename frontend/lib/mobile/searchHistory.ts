// 片名搜索历史：存 localStorage，最多 10 条，最近搜的排最前。
//
// 跨端共用一套：web 发现页搜索框（DiscoverHeader）和移动版底栏片名搜索页
// （MobileDiscoverSearchClient）读写同一份，用户在哪端搜过都能在另一端下拉到。
// 资源搜索页（/m/resource）**不用**它——那页的是关键词回退链，是另一件事。
// 读写都包 try/catch：隐私模式 / SSR 下 localStorage 不可用时静默降级成"没有历史"，
// 不能让搜索框因为读不到历史就崩。

const STORAGE_KEY = "napics_search_history";
export const SEARCH_HISTORY_LIMIT = 10;

/** 读全部历史，最近的在前。读不到或格式坏一律返回空数组。 */
export function readSearchHistory(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is string => typeof x === "string" && x.trim().length > 0)
      .slice(0, SEARCH_HISTORY_LIMIT);
  } catch {
    return [];
  }
}

function write(list: string[]): string[] {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(list)); } catch {}
  return list;
}

/**
 * 记一条搜索词：去重（大小写/首尾空格无关地去重，但存原样）、置顶、截断到上限。
 * 返回更新后的完整列表，供调用方直接 setState。
 */
export function pushSearchHistory(keyword: string): string[] {
  const kw = keyword.trim();
  if (!kw) return readSearchHistory();
  const lower = kw.toLowerCase();
  const rest = readSearchHistory().filter(item => item.toLowerCase() !== lower);
  return write([kw, ...rest].slice(0, SEARCH_HISTORY_LIMIT));
}

/** 删除单条历史词。返回更新后的列表。 */
export function removeSearchHistory(keyword: string): string[] {
  const lower = keyword.trim().toLowerCase();
  const next = readSearchHistory().filter(item => item.toLowerCase() !== lower);
  return write(next);
}

/** 清空全部历史。返回空列表。 */
export function clearSearchHistory(): string[] {
  return write([]);
}
