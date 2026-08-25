// 段级错误边界（app/m/**/error.tsx）共用的展示层。
// 路径解析失败、树加载崩掉都走这里，必须给出"回媒体库"的出路，不能只剩白屏。
"use client";
import { useRouter } from "next/navigation";

import { MOBILE_ROUTES } from "@/lib/mobile/mobileRouteUtils";

export interface MobileErrorFallbackProps {
  error: Error & { digest?: string };
  /** Next 给的重试函数：重新渲染该段 */
  reset: () => void;
  title?: string;
}

export default function MobileErrorFallback({ error, reset, title = "这个页面出错了" }: MobileErrorFallbackProps) {
  const router = useRouter();

  return (
    <div
      className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center"
      role="alert"
      style={{ paddingLeft: "var(--m-page-px)", paddingRight: "var(--m-page-px)" }}
    >
      <h2 className="text-base font-semibold text-[var(--m-text)]">{title}</h2>
      {/* 把真实原因显示出来。只写"出错了"的话，用户和排查的人都拿不到任何线索 */}
      <p className="max-w-full break-words text-xs text-[var(--m-text-dim)]">
        {error.message || "未知错误"}
      </p>
      <div className="flex gap-3">
        <button
          type="button"
          onClick={reset}
          className="rounded-lg px-4 text-sm text-[var(--m-on-accent)]"
          style={{ minHeight: "var(--m-touch-min)", background: "var(--m-accent)" }}
        >
          重试
        </button>
        <button
          type="button"
          onClick={() => router.replace(MOBILE_ROUTES.library)}
          className="rounded-lg px-4 text-sm text-[var(--m-text)]"
          style={{ minHeight: "var(--m-touch-min)", background: "var(--m-surface-raised)" }}
        >
          返回媒体库
        </button>
      </div>
    </div>
  );
}
