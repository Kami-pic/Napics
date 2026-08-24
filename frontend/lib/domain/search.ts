// 搜索域常量：桌面与移动端共用，不得在调用点重复定义。

/**
 * BT 主搜索 SSE 的整体超时（毫秒）。
 * 后端要串行跑多个索引器与直搜源，单次全量搜索本身就慢，
 * 这个值只是兜底，防止连接卡死后界面永远停在"搜索中"。
 */
export const SEARCH_SSE_TIMEOUT_MS = 90000;

/** 送给 AI 推荐的结果条数上限（再多就是白烧 token） */
export const AI_RECOMMEND_RESULT_LIMIT = 20;
