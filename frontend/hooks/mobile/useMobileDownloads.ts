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

  const { hasVideoUnder, reload: reloadTree, version: treeVersion } = useMobileLibraryTree();

  // 代际：轮询响应回来时如果代际已变（刷新过 / 组件重挂载），一律丢弃
  const generationRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tasksRef = useRef<DownloadTask[]>([]);
  // 任务首次归位成功的时刻，用来判断入库确认是否超时
  const relocatedAtRef = useRef<Map<string, number>>(new Map());
  // 已经为哪些任务触发过整树刷新，避免每轮轮询都重拉整棵树
  const treeRefreshedRef = useRef<Set<string>>(new Set());

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
    // 全是终态就不打了 —— progress 有副作用，空转等于让后端白做一轮对账
    if (current.length > 0 && !needsPolling(current)) return;

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

  // 归位成功的任务需要确认是否真的进了媒体库。
  // 每个任务只触发一次整树刷新 —— 整树很贵，不能每轮轮询都拉。
  useEffect(() => {
    let shouldReload = false;
    for (const task of tasks) {
      if (task.relocate_status !== "moved" || !task.save_path) continue;
      if (!relocatedAtRef.current.has(task.id)) {
        relocatedAtRef.current.set(task.id, Date.now());
      }
      if (!hasVideoUnder(task.save_path) && !treeRefreshedRef.current.has(task.id)) {
        treeRefreshedRef.current.add(task.id);
        shouldReload = true;
      }
    }
    if (shouldReload) void reloadTree();
  }, [tasks, hasVideoUnder, reloadTree]);

  // confirming 状态需要随时间推进变成 timeout，否则界面会永远停在"确认中"
  useEffect(() => {
    const waiting = tasks.some(
      task => task.relocate_status === "moved"
        && task.save_path
        && !hasVideoUnder(task.save_path),
    );
    if (!waiting) return;
    const timer = setInterval(() => setClockTick(t => t + 1), 5000);
    return () => clearInterval(timer);
  }, [tasks, hasVideoUnder, treeVersion]);

  const entries = useMemo<MobileDownloadEntry[]>(() => {
    void clockTick;      // 让超时判定随时钟重算
    void treeVersion;    // 树刷新后重算入库状态
    const now = Date.now();

    return tasks.map(task => {
      const status = describeDownloadStatus(task.status);
      const relocate = describeRelocateResult(task);

      let library: LibraryConfirmState = "not_applicable";
      if (task.relocate_status === "moved" && task.save_path) {
        if (hasVideoUnder(task.save_path)) {
          library = "confirmed";
        } else {
          const since = relocatedAtRef.current.get(task.id) ?? now;
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
  }, [tasks, hasVideoUnder, clockTick, treeVersion]);

  return {
    entries,
    loading,
    loadFailed,
    hasAttention: entries.some(entry => entry.needsAttention),
    refresh,
  };
}
