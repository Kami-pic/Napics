// 发现页条目的"本地已有 / 可升级 / 已订阅"角标判定。
//
// 桌面 DiscoverCard 和移动端 MobileDiscoverCard 共用这一份优先级，
// 两端各自决定怎么上色（桌面是 Tailwind 语义色，移动端是 --m-* 变量）。
// 判定逻辑写两份必然会漂：桌面已有五态，移动端漏一态就是"同一批数据显示不一致"。

/** 后端 discover_enrich.inject_local_status 注入的取值 */
export type LocalStatus = "none" | "owned_low" | "owned_high";

export type LocalStatusTagKey = "owned_sub" | "upgrade_sub" | "owned" | "upgrade" | "subscribed";

/** 三种语义色：已有 / 可升级 / 订阅。两端各自映射到自己的色板 */
export type LocalStatusTone = "owned" | "upgrade" | "subscribe";

export interface LocalStatusTag {
  key: LocalStatusTagKey;
  text: string;
  tone: LocalStatusTone;
}

/**
 * 优先级：已有+订阅 > 可升级+订阅 > 已有 > 可升级 > 仅订阅。
 * 都不满足返回 null（不显示角标，不显示"未拥有"这类噪音）。
 */
export function resolveLocalStatusTag(
  localStatus?: string,
  isSubscribed?: boolean,
): LocalStatusTag | null {
  if (localStatus === "owned_high") {
    return isSubscribed
      ? { key: "owned_sub", text: "✓ 已有·订阅", tone: "owned" }
      : { key: "owned", text: "✓ 已有", tone: "owned" };
  }
  if (localStatus === "owned_low") {
    return isSubscribed
      ? { key: "upgrade_sub", text: "↑ 升级·订阅", tone: "upgrade" }
      : { key: "upgrade", text: "↑ 可升级", tone: "upgrade" };
  }
  return isSubscribed ? { key: "subscribed", text: "📌 已订阅", tone: "subscribe" } : null;
}
