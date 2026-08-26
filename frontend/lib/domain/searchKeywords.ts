// 搜索词回退链：把各源上报的「试过哪些词、哪个词命中」汇总成一条可显示的链。
//
// 桌面搜索弹窗与移动端资源搜索页共用这一份。为什么必须显性化：BT 搜索会按
// 中文名 → 英文名 → 原名 → 去季号 等策略连着试好几个词，用户看到「没有结果」时
// 第一个要问的就是"你到底拿什么词搜的"。不给这条链，他只能猜。

export interface SearchKeywordChainItem {
  keyword: string;
  /** 这个词是否有源真的命中了结果 */
  hit: boolean;
}

/** 各源上报的搜索词信息（`useSearchState.sourceKeywordInfo`） */
export type SourceKeywordInfo = Record<string, { searched: string[]; hit: string }>;

/**
 * 汇总成一条链：**未命中的排在前面，命中的排在后面**。
 *
 * 顺序不是按时间而是按结果：回退链本来就是"先试窄的，不行再放宽"，
 * 把命中的放在末尾，读起来就是"这几个都没有，最后靠这个找到了"。
 * 同一个词被多个源试过只显示一次。
 */
export function buildKeywordChain(info: SourceKeywordInfo): SearchKeywordChainItem[] {
  const ordered: string[] = [];
  const seen = new Set<string>();
  const hits = new Set<string>();

  for (const entry of Object.values(info || {})) {
    for (const keyword of entry?.searched || []) {
      if (!keyword || seen.has(keyword)) continue;
      seen.add(keyword);
      ordered.push(keyword);
    }
    if (entry?.hit) hits.add(entry.hit);
  }

  const notHit = ordered.filter(kw => !hits.has(kw));
  const hit = ordered.filter(kw => hits.has(kw));
  return [...notHit, ...hit].map(keyword => ({ keyword, hit: hits.has(keyword) }));
}
