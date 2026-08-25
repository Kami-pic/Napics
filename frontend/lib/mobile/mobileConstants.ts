// 移动端常量：**只放 JS 逻辑真正读取的值**。
// 颜色、底栏高度、安全区、触控目标这些只有 CSS 用的，一律在 globals.css 的
// --m-* 变量里，不在这里重复一份（两处定义必然对不上）。

/** 媒体卡片网格列数。竖屏两列是海报比例下的可点面积与信息量平衡点 */
export const MOBILE_GRID_COLUMNS = 2;

/** 发现页每次加载的条目数。固定值，不跟视口列数联动 —— 桌面的 useDiscoverState
 *  就是因为把分页量绑在列数上，横竖屏切换会清缓存重拉。 */
export const MOBILE_DISCOVER_PAGE_SIZE = 20;
