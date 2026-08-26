// 媒体卡片网格：一行三张。
//
// 三列而不是单列列表：一屏能看到的条目数翻三倍，而且海报本身就是最快的识别通道 ——
// 原始文件名很长，纯文字列表里前 20 个字往往都是同一个剧名。
"use client";
import type { ReactNode } from "react";

import { MOBILE_GRID_COLUMNS } from "@/lib/mobile/mobileConstants";

export interface MobileCardGridProps {
  children: ReactNode;
  /** 分段标题，如"其他视频（剧场版 / 特别篇）" */
  title?: string;
  ariaLabel?: string;
}

export default function MobileCardGrid({ children, title, ariaLabel }: MobileCardGridProps) {
  return (
    <section className="flex flex-col gap-2">
      {title && <h2 className="px-1 text-[12px] text-[var(--m-text-dim)]">{title}</h2>}
      <div
        className="grid gap-2"
        style={{ gridTemplateColumns: `repeat(${MOBILE_GRID_COLUMNS}, minmax(0, 1fr))` }}
        aria-label={ariaLabel || title}
      >
        {children}
      </div>
    </section>
  );
}
