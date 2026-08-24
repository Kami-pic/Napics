// 搜索的取消与代际门禁 —— 从 useSearchState 拆出。
//
// 原设计把清理绑在"弹窗关闭"上，路由搜索页没有这个时机（组件常驻、只有 query 变化和卸载），
// 所以取消能力必须独立于 open 存在。
//
// 代际（generation）只在**发起一次新的全量搜索**时递增：同一 query 下切 Tab 触发的
// 网盘 / 单源搜索属于同一代，不该互相打断。各通道各持一个 AbortController，
// 通道内的新请求只取消自己通道的旧请求。
"use client";
import { useCallback, useEffect, useRef } from "react";

export interface SearchLifecycle {
  /** 当前代际号；旧响应发现代际不匹配就必须放弃写 state */
  generationRef: React.RefObject<number>;
  /** 当前 BT 主搜索的 SSE 连接 */
  activeEsRef: React.RefObject<EventSource | null>;
  /** 递增代际 + 取消全部在途请求，返回本次搜索的代际号 */
  beginNewSearch: () => number;
  /** 幂等取消：关 SSE、清 timeout、abort 三个通道，并递增代际让残留响应失效 */
  cancelCurrentSearch: () => void;
  /** 挂 SSE 超时；同一时刻只允许一个 */
  setSseTimeout: (fn: () => void, ms: number) => void;
  clearSseTimeout: () => void;
  /** 仅当 ref 仍指向这个连接、且代际未变时才置空，避免抹掉新搜索刚写入的 ref */
  releaseEventSource: (es: EventSource, generation: number) => void;
  /** 取一个新的通道 controller，同时 abort 该通道的上一个 */
  nextController: (channel: SearchChannel) => AbortController;
}

export type SearchChannel = "bt" | "pan" | "source";

export function useSearchLifecycle(): SearchLifecycle {
  const generationRef = useRef(0);
  const activeEsRef = useRef<EventSource | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const controllersRef = useRef<Record<SearchChannel, AbortController | null>>({
    bt: null, pan: null, source: null,
  });

  const clearSseTimeout = useCallback(() => {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const setSseTimeout = useCallback((fn: () => void, ms: number) => {
    clearSseTimeout();
    timeoutRef.current = setTimeout(fn, ms);
  }, [clearSseTimeout]);

  const abortChannel = useCallback((channel: SearchChannel) => {
    const controller = controllersRef.current[channel];
    if (controller) {
      controller.abort();
      controllersRef.current[channel] = null;
    }
  }, []);

  const nextController = useCallback((channel: SearchChannel) => {
    abortChannel(channel);
    const controller = new AbortController();
    controllersRef.current[channel] = controller;
    return controller;
  }, [abortChannel]);

  const cancelCurrentSearch = useCallback(() => {
    generationRef.current++;
    if (activeEsRef.current) {
      activeEsRef.current.close();
      activeEsRef.current = null;
    }
    clearSseTimeout();
    abortChannel("bt");
    abortChannel("pan");
    abortChannel("source");
  }, [abortChannel, clearSseTimeout]);

  const beginNewSearch = useCallback(() => {
    cancelCurrentSearch();
    return generationRef.current;
  }, [cancelCurrentSearch]);

  const releaseEventSource = useCallback((es: EventSource, generation: number) => {
    if (activeEsRef.current === es && generationRef.current === generation) {
      activeEsRef.current = null;
    }
  }, []);

  // 卸载和页面隐藏都要断流：移动端切后台 / 息屏走 pagehide，
  // 而 iOS Safari 上 unload 不可靠，只能靠 pagehide。
  useEffect(() => {
    const onPageHide = () => cancelCurrentSearch();
    window.addEventListener("pagehide", onPageHide);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      cancelCurrentSearch();
    };
  }, [cancelCurrentSearch]);

  return {
    generationRef, activeEsRef,
    beginNewSearch, cancelCurrentSearch,
    setSseTimeout, clearSseTimeout,
    releaseEventSource, nextController,
  };
}
