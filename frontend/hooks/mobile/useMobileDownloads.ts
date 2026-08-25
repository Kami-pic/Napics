// 移动端下载任务：完整任务列表 + 轮询驱动对账 + 入库确认。
//
// 两个接口的分工不能搞混：
// - /download-manager/tasks    完整任务事实来源
// - /download-manager/progress **带副作用的 GET**，触发对账、状态落盘和归位，
//   但只返回 downloading / unknown 子集
// 所以轮询停止 = 对账与归位停止，而 progress 的返回只能按 id 合并进列表。
"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { DownloadTask } from "@/types";
import { api } from "@/lib/api";
import {
  DOWNLOAD_POLL_INTERVAL_MS,
  describeDownloadStatus,
  describeRelocateResult,
  mergeProgressIntoTasks,
  needsPolling,
  type DownloadStatusMeta,
  type RelocateHint,
} from "@/lib/domain/download";
import { useMobileLibraryTree } from "@/components/mobile/MobileLibraryTreeProvider";

/** 归位完成后等多久还没在媒体库里看到文件，就提示用户手动同步 */
export const LIBRARY_CONFIRM_TIMEOUT_MS = 60_000;

/** 整树刷新的重试退避（毫秒）。
 *  后端的局部刷新是跑 ffprobe 的后台线程，前端第一次拉树时它往往还没写库。
 *  只刷一次就再也不刷，确认状态会没有任何自愈路径、一律走到超时。
 *  整树请求不便宜，所以按退避重试而不是每轮都拉。 */
const TREE_RETRY_DELAYS_MS = [3_000, 6_000, 12_000, 24_000];

/** 入库确认状态。completed 不等于已入库，中间还有归位 + 局部刷新两步异步 */
export type LibraryConfirmState =
  | "not_applicable"   // 还没归位成功，谈不上入库
  | "confirming"       // 已归位，等媒体库出现这个文件
  | "confirmed"        // 树里已经能看到
  | "timeout";         // 等太久了，需要手动同步

export interface MobileDownloadEntry {
  task: DownloadTask;
  status: DownloadStatusMeta;
  relocate: RelocateHint | null;
  library: LibraryConfirmState;
  /** 是否需要用户介入（归位没搬动、归位失败、入库确认超时、任务报错） */
  needsAttention: boolean;
}

export interface MobileDownloadsState {
  entries: MobileDownloadEntry[];
  loading: boolean;
  loadFailed: boolean;
  /** 是否有任何条目需要用户介入 —— 决定要不要显示"快速同步"恢复入口 */
  hasAttention: boolean;
  /** 重新拉取完整任务列表 */
  refresh: () => Promise<void>;
}

export function useMobileDownloads(): MobileDownloadsState {
  const [tasks, setTasks] = useState<DownloadTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  // 让 confirming → timeout 的判定能重新计算
  const [clockTick, setClockTick] = useState(0);

  const { hasVideoPath, hasVideoUnder, reload: reloadTree, version: treeVersion } = useMobileLibraryTree();

  /** 归位过去的东西是否已经在库里。
   *  逐条按精确路径判断：条目是文件就查路径本身，是目录就查它下面有没有视频。
   *  拿不到 relocated_files（旧任务）时才退回"save_path 下有没有视频"这个粗判据。 */
  const isInLibrary = useCallback((task: DownloadTask) => {
    const paths = task.relocated_files ?? [];
    if (paths.length === 0) return hasVideoUnder(task.save_path);
    return paths.some(path => hasVideoPath(path) || hasVideoUnder(path));
  }, [hasVideoPath, hasVideoUnder]);

  // 代际：轮询响应回来时如果代际已变（刷新过 / 组件重挂载），一律丢弃
  const generationRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tasksRef = useRef<DownloadTask[]>([]);
  // 后端没给 relocated_at 的旧任务，退回用"前端首次观察到 moved"的时刻
  const fallbackRelocatedAtRef = useRef<Map<string, number>>(new Map());
  // 每个任务的整树刷新记录：试了几次、上次什么时候。用于退避重试
  const treeRetryRef = useRef<Map<string, { attempts: number; lastAt: number }>>(new Map());

  // 轮询回调需要读到最新任务列表，但它挂在 timer 上不参与渲染，所以走 ref。
  // 在 effect 里同步而不是渲染期直接写：渲染期写外部状态是 react-hooks 明确禁止的。
  useEffect(() => { tasksRef.current = tasks; }, [tasks]);

  const refresh = useCallback(async () => {
    const generation = ++generationRef.current;
    setLoading(true);
    try {
      const res = await api.getDownloadTasks();
      if (generationRef.current !== generation) return;
      setTasks(res.tasks || []);
      setLoadFailed(false);
    } catch {
      if (generationRef.current !== generation) return;
      setLoadFailed(true);
    } finally {
      if (generationRef.current === generation) setLoading(false);
    }
  }, []);

  /** 一次轮询：progress 驱动对账，返回值只合并不替换 */
  const pollOnce = useCallback(async () => {
    const current = tasksRef.current;
    // 没有任何需要驱动的任务就不打了 —— progress 是带副作用的 GET，
    // 空转等于让后端白做一轮对账。零任务和加载失败也算没有需要驱动的。
    if (!needsPolling(current)) return;

    const generation = generationRef.current;
    try {
      const res = await api.getDownloadProgress();
      if (generationRef.current !== generation) return;
      setTasks(prev => mergeProgressIntoTasks(prev, res.tasks || []));
    } catch {
      // 单次轮询失败不改变列表，也不弹错误：下一轮可能就好了
    }
  }, []);

  // 轮询生命周期由这个 hook 独占：页面可见时跑，隐藏和卸载时停
  useEffect(() => {
    const start = () => {
      if (timerRef.current) return;   // 防止重复 timer
      timerRef.current = setInterval(() => { void pollOnce(); }, DOWNLOAD_POLL_INTERVAL_MS);
    };
    const stop = () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void pollOnce();   // 回到前台先补一次，不用等下一个 tick
        start();
      } else {
        stop();
      }
    };

    void refresh();
    if (document.visibilityState === "visible") start();
    document.addEventListener("visibilitychange", onVisibilityChange);

    // 捕获 ref 容器本身（它是稳定的），cleanup 里递增的就是最新代际
    const generation = generationRef;
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      stop();
      generation.current++;   // 卸载后到达的响应一律作废
    };
  }, [pollOnce, refresh]);

  /** 归位时刻：优先用后端记的，页面重开后不会重新数一遍超时 */
  const relocatedAt = useCallback((task: DownloadTask) => {
    if (task.relocated_at) {
      const parsed = Date.parse(task.relocated_at);
      if (Number.isFinite(parsed)) return parsed;
    }
    let fallback = fallbackRelocatedAtRef.current.get(task.id);
    if (fallback === undefined) {
      fallback = Date.now();
      fallbackRelocatedAtRef.current.set(task.id, fallback);
    }
    return fallback;
  }, []);

  // 归位成功但库里还看不到的任务，按退避重新拉树。
  // 后端局部刷新是跑 ffprobe 的后台线程，第一次拉树时它往往还没写完库。
  useEffect(() => {
    const now = Date.now();
    let shouldReload = false;

    for (const task of tasks) {
      if (task.relocate_status !== "moved" || !task.save_path) continue;
      if (isInLibrary(task)) {
        treeRetryRef.current.delete(task.id);
        continue;
      }
      // 超时之后不再重试，交给用户手动同步
      if (now - relocatedAt(task) > LIBRARY_CONFIRM_TIMEOUT_MS) continue;

      const record = treeRetryRef.current.get(task.id);
      if (!record) {
        treeRetryRef.current.set(task.id, { attempts: 1, lastAt: now });
        shouldReload = true;
        continue;
      }
      const delay = TREE_RETRY_DELAYS_MS[Math.min(record.attempts, TREE_RETRY_DELAYS_MS.length - 1)];
      if (now - record.lastAt >= delay) {
        treeRetryRef.current.set(task.id, { attempts: record.attempts + 1, lastAt: now });
        shouldReload = true;
      }
    }

    if (shouldReload) void reloadTree();
  }, [tasks, clockTick, isInLibrary, relocatedAt, reloadTree]);

  // 推动时钟：confirming 既要能变成 timeout，也要能触发上面的退避重试。
  // 依赖只放布尔量 —— 放 tasks 的话这个 interval 会被每轮轮询拆掉重建，一次都触发不了。
  const waitingForLibrary = tasks.some(
    task => task.relocate_status === "moved" && task.save_path && !isInLibrary(task),
  );
  useEffect(() => {
    if (!waitingForLibrary) return;
    const timer = setInterval(() => setClockTick(t => t + 1), 3000);
    return () => clearInterval(timer);
  }, [waitingForLibrary]);

  const entries = useMemo<MobileDownloadEntry[]>(() => {
    void clockTick;      // 让超时判定随时钟重算
    void treeVersion;    // 树刷新后重算入库状态
    const now = Date.now();

    return tasks.map(task => {
      const status = describeDownloadStatus(task.status);
      const relocate = describeRelocateResult(task);

      let library: LibraryConfirmState = "not_applicable";
      if (task.relocate_status === "moved" && task.save_path) {
        if (isInLibrary(task)) {
          library = "confirmed";
        } else {
          const since = relocatedAt(task);
          library = now - since > LIBRARY_CONFIRM_TIMEOUT_MS ? "timeout" : "confirming";
        }
      }

      const needsAttention = Boolean(
        relocate?.actionable
        || library === "timeout"
        || status.tone === "danger"
        || task.error,
      );

      return { task, status, relocate, library, needsAttention };
    });
  }, [tasks, isInLibrary, relocatedAt, clockTick, treeVersion]);

  return {
    entries,
    loading,
    loadFailed,
    hasAttention: entries.some(entry => entry.needsAttention),
    refresh,
  };
}
