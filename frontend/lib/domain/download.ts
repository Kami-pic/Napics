// 下载域：状态语义、轮询间隔、任务合并规则。桌面与移动端共用。
//
// 这里只返回**语义 variant**（tone），不返回 Tailwind class 或色值 ——
// 桌面和移动端的配色体系不同，class 留给各自的视图层决定。

import type { DownloadTask } from "@/types";

/**
 * 轮询间隔。
 *
 * `/download-manager/progress` 是**带副作用的 GET**：它触发 sync_progress 对账、
 * 状态落盘和归位。所以轮询停止 = 对账与归位停止，不只是界面不刷新。
 *
 * 已知行为（P0 接受，不规避）：桌面面板和移动端下载页同时打开时，
 * 对账会被双倍触发。后端每次对账是幂等的，重复只是多几次 qB 查询。
 */
export const DOWNLOAD_POLL_INTERVAL_MS = 4000;

export type DownloadStatus = DownloadTask["status"];

/** 语义色调，由视图层翻译成自己的配色 */
export type DownloadTone = "pending" | "active" | "success" | "warning" | "danger" | "muted";

export interface DownloadStatusMeta {
  label: string;
  tone: DownloadTone;
  /** 终态：不会再自己变化 */
  terminal: boolean;
  /**
   * 对账态：状态还没确定。
   * lost / unknown 属于这一类 —— **不能显示成失败**，
   * 它们只表示"下载器里暂时查不到这个任务"，下一轮对账可能就恢复了。
   */
  reconciling: boolean;
}

/**
 * 后端 status 的全部取值，一个不少一个不多。
 *
 * 用 Record<DownloadStatus, …> 而不是 Record<string, …>：新增取值时类型检查会报错，
 * 不会静默落进 default 变成空白标签。
 *
 * `relocating` / `cloud_done` **不在这里** —— 后端状态机 docstring 和桌面旧映射
 * 里留着它们，但全代码库没有任何赋值点，是过期文档和死配置。
 */
export const DOWNLOAD_STATUS_META: Record<DownloadStatus, DownloadStatusMeta> = {
  pending: { label: "等待中", tone: "pending", terminal: false, reconciling: false },
  downloading: { label: "下载中", tone: "active", terminal: false, reconciling: false },
  completed: { label: "已完成", tone: "success", terminal: true, reconciling: false },
  awaiting_confirm: { label: "待整理", tone: "warning", terminal: false, reconciling: false },
  archived: { label: "已归档", tone: "muted", terminal: true, reconciling: false },
  failed: { label: "失败", tone: "danger", terminal: true, reconciling: false },
  cancelled: { label: "已取消", tone: "muted", terminal: true, reconciling: false },
  // 下面两个是对账中，不是失败
  lost: { label: "正在核对", tone: "warning", terminal: false, reconciling: true },
  unknown: { label: "状态待确认", tone: "warning", terminal: false, reconciling: true },
};

/** 后端将来加了新取值时的兜底：显示原始值，不给空白标签 */
export function describeDownloadStatus(status: string): DownloadStatusMeta {
  return (
    DOWNLOAD_STATUS_META[status as DownloadStatus]
    ?? { label: status || "未知状态", tone: "muted", terminal: false, reconciling: true }
  );
}

/** 是否还需要轮询驱动（终态就不用再打 progress 了） */
export function needsPolling(tasks: readonly Pick<DownloadTask, "status">[]): boolean {
  return tasks.some(task => !describeDownloadStatus(task.status).terminal);
}

/**
 * 真正失败的任务 id。
 *
 * 判据是 `tone === "danger"` 而不是硬编码 `status === "failed"`：后端将来把某个
 * 状态标成失败时自动纳入，不用再改这里。
 *
 * **lost / unknown 不算失败** —— 它们是对账态，下一轮对账可能就恢复了。
 * 清理时把它们一起删掉，等于把正在核对的任务记录抹了。
 */
export function collectFailedTaskIds(
  tasks: readonly Pick<DownloadTask, "id" | "status">[],
): string[] {
  return tasks
    .filter(task => describeDownloadStatus(task.status).tone === "danger")
    .map(task => task.id);
}

/**
 * 可以清理的「已处理」任务 id：终态任务。
 *
 * 原来这里硬编码的列表里含 lost / unknown，而那两个是对账态、terminal 为 false ——
 * 「清除已完成」会顺手删掉正在核对的任务。
 */
export function collectClearableTaskIds(
  tasks: readonly Pick<DownloadTask, "id" | "status">[],
): string[] {
  return tasks
    .filter(task => describeDownloadStatus(task.status).terminal)
    .map(task => task.id);
}

/**
 * 把 `/download-manager/progress` 的返回合并进已有任务列表。
 *
 * **形状陷阱**：两个接口都返回 key 为 `tasks` 的数组，形状相同但语义不同 ——
 * progress 只含 downloading / unknown 子集。直接 `setTasks(res.tasks)`
 * 会把已完成的任务从界面上抹掉。所以只允许按 id 合并，永不整体替换。
 */
export function mergeProgressIntoTasks<T extends { id: string }>(
  tasks: readonly T[],
  progressTasks: readonly Partial<T>[],
): T[] {
  const byId = new Map<string, Partial<T>>();
  for (const item of progressTasks) {
    if (item?.id) byId.set(item.id, item);
  }
  // 空 patch 时返回原数组：返回新数组会让调用方每次轮询都触发一次
  // 无意义的重渲染，下游 memo 和 effect 跟着全部重算
  if (byId.size === 0) return tasks as T[];
  return tasks.map(task => {
    const patch = byId.get(task.id);
    return patch ? { ...task, ...patch } : task;
  });
}

// ── 归位结果 ──

export interface RelocateHint {
  label: string;
  tone: DownloadTone;
  /** 需要用户介入（提示"快速同步"或手动处理） */
  actionable: boolean;
}

/**
 * 归位结果的人话描述。
 *
 * status 为 completed 只代表下载器侧完成，**不代表文件已经到 save_path**。
 * 没有这个区分，"归位成功"和"一个文件都没搬"在界面上长得一模一样。
 */
export function describeRelocateResult(
  task: Pick<DownloadTask, "relocate_status" | "relocated_count">,
): RelocateHint | null {
  switch (task.relocate_status) {
    case "moved":
      return {
        label: `已归位 ${task.relocated_count} 个文件`,
        tone: "success",
        actionable: false,
      };
    case "skipped_existing":
      return {
        label: "目标目录已有同名文件，未搬动",
        tone: "warning",
        actionable: true,
      };
    case "empty":
      return {
        label: "下载目录里没有文件，归位未执行",
        tone: "warning",
        actionable: true,
      };
    case "failed":
      return { label: "归位失败", tone: "danger", actionable: true };
    case "":
      return null;
    default:
      return null;
  }
}
