// 加载 / 空 / 错误 / 就绪 四态的统一呈现。
// 只有这一个组件负责这四种状态，不要在各页面各写一套骨架屏和空状态。
"use client";
import type { ReactNode } from "react";

export type MobileViewState = "loading" | "empty" | "error" | "ready";

export interface MobileStateViewProps {
  state: MobileViewState;
  /** state 为 ready 时渲染 */
  children?: ReactNode;
  loadingText?: string;
  emptyText?: string;
  /** 错误详情。拿不到时也要给一句人能看懂的话，不留白屏 */
  errorText?: string;
  /** 空状态下的引导操作，如"去搜索" */
  emptyAction?: ReactNode;
  onRetry?: () => void;
}

export default function MobileStateView({
  state,
  children,
  loadingText = "加载中…",
  emptyText = "这里还没有内容",
  errorText = "加载失败",
  emptyAction,
  onRetry,
}: MobileStateViewProps) {
  if (state === "ready") return <>{children}</>;

  return (
    <div
      className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center"
      role={state === "error" ? "alert" : "status"}
      aria-live={state === "loading" ? "polite" : undefined}
    >
      {state === "loading" && (
        <>
          <span
            className="h-6 w-6 animate-spin rounded-full border-2 border-t-transparent"
            style={{ borderColor: "var(--m-border-strong)", borderTopColor: "transparent" }}
            aria-hidden="true"
          />
          <p className="text-sm text-[var(--m-text-muted)]">{loadingText}</p>
        </>
      )}

      {state === "empty" && (
        <>
          <p className="text-sm text-[var(--m-text-muted)]">{emptyText}</p>
          {emptyAction}
        </>
      )}

      {state === "error" && (
        <>
          <p className="text-sm text-[var(--m-danger)]">{errorText}</p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="rounded-lg px-4 text-sm text-[var(--m-text)]"
              style={{
                minHeight: "var(--m-touch-min)",
                background: "var(--m-surface-raised)",
              }}
            >
              重试
            </button>
          )}
        </>
      )}
    </div>
  );
}
