// 快速同步（/sync）—— 自动入库失败、归位没搬动、外部新增文件时的恢复入口。
//
// /sync 是**请求内 SSE**：连接断了就没了，服务端不会替你继续。所以页面离开、
// 切后台、网络中断都必须表达成"结果未知"，不能提示"任务仍会在服务端继续"。
"use client";
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { iterSseEvents } from "@/lib/sse/framer";
import { useMobileLibraryTree } from "@/components/mobile/MobileLibraryTreeProvider";

export type QuickSyncPhase =
  | "idle"
  | "running"
  | "done"          // 收到了 done 事件，结果确定
  | "interrupted"   // 流断了但没收到 done，结果未知
  | "failed";       // 请求本身失败

export interface MobileQuickSyncState {
  phase: QuickSyncPhase;
  /** 进度或结果文案，直接给用户看 */
  message: string;
  running: boolean;
  /** 触发同步。已在进行中时直接返回，不叠加请求 */
  run: () => Promise<void>;
}

interface SyncEvent {
  type?: "status" | "progress" | "done" | "error";
  message?: string;
  current?: number;
  total?: number;
  file?: string;
  added?: number;
  removed?: number;
}

export function useMobileQuickSync(): MobileQuickSyncState {
  const [phase, setPhase] = useState<QuickSyncPhase>("idle");
  const [message, setMessage] = useState("");
  const { reload: reloadTree } = useMobileLibraryTree();

  const abortRef = useRef<AbortController | null>(null);
  const runningRef = useRef(false);

  // 离开页面就断流。移动端 Safari 上 unload 不可靠，只能靠 pagehide
  useEffect(() => {
    const cancel = () => abortRef.current?.abort();
    window.addEventListener("pagehide", cancel);
    return () => {
      window.removeEventListener("pagehide", cancel);
      cancel();
    };
  }, []);

  const run = useCallback(async () => {
    if (runningRef.current) return;   // 重复点击直接忽略
    runningRef.current = true;

    const controller = new AbortController();
    abortRef.current = controller;
    setPhase("running");
    setMessage("正在同步…");

    let sawDone = false;
    try {
      const response = await api.quickSync(controller.signal);
      if (!response.ok) {
        setPhase("failed");
        setMessage(`同步请求失败（HTTP ${response.status}）`);
        return;
      }
      if (!response.body) {
        setPhase("interrupted");
        setMessage("服务端没有返回数据流，同步结果未知");
        return;
      }

      for await (const part of iterSseEvents(response.body, controller.signal)) {
        if (!part.startsWith("data: ")) continue;
        // framer 会吐出流末尾未闭合的残留，这里可能是半截 JSON
        let data: SyncEvent;
        try { data = JSON.parse(part.replace("data: ", "")); } catch { continue; }

        if (data.type === "status") {
          setMessage(data.message || "正在同步…");
        } else if (data.type === "progress") {
          setMessage(`正在分析 ${data.current ?? 0}/${data.total ?? 0}`);
        } else if (data.type === "error") {
          sawDone = true;   // 服务端明确报错也算有结论
          setPhase("failed");
          setMessage(data.message || "同步失败");
        } else if (data.type === "done") {
          sawDone = true;
          setPhase("done");
          setMessage(`同步完成：新增 ${data.added ?? 0}，移除 ${data.removed ?? 0}`);
          // 只有拿到 done 才刷新缓存 —— 结果未知时不能预先宣称成功
          await reloadTree();
        }
      }

      if (!sawDone) {
        setPhase("interrupted");
        setMessage("连接中断，同步结果未知。重新进入页面后按媒体库实际内容判断");
      }
    } catch (e) {
      if (controller.signal.aborted) {
        setPhase("interrupted");
        setMessage("同步被中断，结果未知");
      } else {
        setPhase("failed");
        setMessage(e instanceof Error ? `同步失败：${e.message}` : "同步失败");
      }
    } finally {
      runningRef.current = false;
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [reloadTree]);

  return { phase, message, running: phase === "running", run };
}
