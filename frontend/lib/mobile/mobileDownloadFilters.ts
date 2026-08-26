// 下载任务的筛选分类。
//
// 三类互斥，且并集等于全部：读到"需处理 2"时用户能确信另外几类里没有藏着要处理的任务。
// 判定顺序上"需处理"优先 —— 一个 failed 任务同时是终态，但它不该出现在「已完成」里。
import type { MobileDownloadEntry } from "@/hooks/mobile/useMobileDownloads";

/** `done` 是"已结束"（完成 / 取消 / 归档），不是"成功完成" */
export type MobileDownloadFilterKey = "all" | "active" | "attention" | "done";

export const MOBILE_DOWNLOAD_FILTERS: { key: MobileDownloadFilterKey; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "active", label: "进行中" },
  { key: "attention", label: "需处理" },
  // 叫「已结束」而不是「已完成」：这一类按终态划分，除了 completed 还包含
  // cancelled 与 archived。把已取消的任务放进「已完成」是在骗人。
  { key: "done", label: "已结束" },
];

/**
 * 条目归哪一类。
 *
 * 进行中包含 pending / downloading / awaiting_confirm，也包含 lost / unknown ——
 * 后两个是**对账中**不是失败，不能塞进「需处理」让用户白操心。
 */
export function downloadEntryCategory(
  entry: MobileDownloadEntry,
): Exclude<MobileDownloadFilterKey, "all"> {
  if (entry.needsAttention) return "attention";
  return entry.status.terminal ? "done" : "active";
}

export function matchesDownloadFilter(
  entry: MobileDownloadEntry,
  filter: MobileDownloadFilterKey,
): boolean {
  return filter === "all" || downloadEntryCategory(entry) === filter;
}

/** 每个筛选项的条目数，直接标在 chip 上 */
export function countByDownloadFilter(
  entries: readonly MobileDownloadEntry[],
): Record<MobileDownloadFilterKey, number> {
  const counts: Record<MobileDownloadFilterKey, number> = {
    all: entries.length, active: 0, attention: 0, done: 0,
  };
  for (const entry of entries) counts[downloadEntryCategory(entry)] += 1;
  return counts;
}
