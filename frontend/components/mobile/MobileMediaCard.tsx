// 媒体卡片（memo：一屏三十来张，切目录时不该整批重渲染）。
//
// 视觉与桌面 CardGrid 对齐：2:3 海报 + 底部渐变压字 + 左上角徽标 + 右上角质量标签。
// 信息口径在 lib/mobile/mobileCardMeta.ts，这里只负责画。
//
// 封面**不做**桌面那套"本地失败就读 NFO 拿远程 URL"的二次请求：
// 一屏三十张卡各发一个 /scrape/read，在 NAS 链路上是几十次串行文件读。
// 拿不到本地封面就显示文字占位。
"use client";
import { memo, useState } from "react";

import { api } from "@/lib/api";
import type { MobileCardBadgeTone, MobileCardMeta, MobileCardTag } from "@/lib/mobile/mobileCardMeta";

const BADGE_TONE: Record<MobileCardBadgeTone, string> = {
  episodes: "var(--m-success)",
  series: "var(--m-accent)",
  collection: "var(--m-text-muted)",
  library: "var(--m-accent)",
  // 一级分类标签：与桌面 CategoryTagBadge 同配色（电影类蓝、其他绿）
  categoryMovie: "var(--m-accent)",
  categoryTv: "var(--m-success)",
};

const TAG_TONE: Record<MobileCardTag["tone"], string> = {
  warning: "var(--m-warning)",
  hdr: "var(--m-violet)",
  muted: "var(--m-text-dim)",
  danger: "var(--m-danger)",
};

export interface MobileMediaCardProps {
  meta: MobileCardMeta;
  onOpen: () => void;
  /** 传了才渲染右下角播放键（视频卡才有） */
  onPlay?: () => void;
}

const MobileMediaCard = memo(function MobileMediaCard({ meta, onOpen, onPlay }: MobileMediaCardProps) {
  const [failed, setFailed] = useState(false);
  const src = meta.posterPath && !failed ? api.getLocalPoster(meta.posterPath, meta.cover) : "";

  return (
    <div className="relative">
      {/* 不设 aria-label：它会覆盖子元素文本，把徽标（S01 · 12 集）、
          分辨率 · 大小、低画质/HDR 全部从可访问名里吞掉。让内部文本自然拼成名字。 */}
      <button
        type="button"
        onClick={onOpen}
        className="block w-full overflow-hidden rounded-[var(--m-radius)] text-left active:opacity-80"
        style={{ background: "var(--m-surface)", border: "1px solid var(--m-border)" }}
      >
        <span
          className="relative block w-full"
          style={{ aspectRatio: "2 / 3", background: "var(--m-surface-raised)" }}
        >
          {src ? (
            // eslint-disable-next-line @next/next/no-img-element -- 走后端图片代理，不进 next/image
            <img
              src={src}
              alt=""
              loading="lazy"
              decoding="async"
              className="h-full w-full object-cover"
              onError={() => setFailed(true)}
            />
          ) : (
            // 实测全库约三分之一的条目没有本地封面（未刮削的散片、聚合容器）。
            // 占位不重复标题 —— 标题在卡片下方本来就有两行，重复一遍等于白占一屏。
            // 和桌面 CardGrid 的 🎬 占位保持一致。
            <span
              className="flex h-full w-full items-center justify-center text-[28px] opacity-25"
              aria-hidden="true"
            >
              🎬
            </span>
          )}

          {meta.badge && meta.badge.text && (
            <span
              className="absolute left-1 top-1 rounded-[var(--m-radius-sm)] px-1 py-0.5 text-[10px] font-medium leading-none"
              style={{ background: "var(--m-overlay)", color: BADGE_TONE[meta.badge.tone] }}
            >
              {meta.badge.text}
            </span>
          )}

          {meta.tags.length > 0 && (
            <span className="absolute right-1 top-1 flex flex-col items-end gap-0.5">
              {meta.tags.map(tag => (
                <span
                  key={tag.text}
                  className="rounded-[var(--m-radius-sm)] px-1 py-0.5 text-[10px] font-medium leading-none"
                  style={{ background: "var(--m-overlay)", color: TAG_TONE[tag.tone] }}
                >
                  {tag.text}
                </span>
              ))}
            </span>
          )}
        </span>

        <span className="flex min-w-0 flex-col gap-0.5 px-1.5 pb-1.5 pt-1">
          {/* 原始文件名很长，两行截断比单行截断能认出的信息多得多 */}
          <span className="line-clamp-2 text-[12px] leading-snug text-[var(--m-text)]">{meta.title}</span>
          {meta.subtitle && (
            <span className="truncate text-[10px] text-[var(--m-text-dim)]">{meta.subtitle}</span>
          )}
        </span>
      </button>

      {/* 播放键浮在海报右下角。卡片本体进详情，这里直接开播 —— 和原来列表行尾一个语义。
          它不能放进卡片那个 <button> 里（嵌套按钮非法），所以用一个与海报同比例的
          定位层来对齐：inset-x-0 + top-0 + aspect-ratio 2/3 得到的高度就是海报高度，
          于是按钮位置与标题占几行完全无关（早先用 `bottom: calc(100% - 66%)` 是相对
          整张卡算的，标题从两行变一行按钮就会漂移）。 */}
      {onPlay && (
        <div
          className="pointer-events-none absolute inset-x-0 top-0"
          style={{ aspectRatio: "2 / 3" }}
        >
          <button
            type="button"
            onClick={onPlay}
            aria-label={`播放 ${meta.title}`}
            className="pointer-events-auto absolute bottom-1 right-1 flex items-center justify-center rounded-[var(--m-radius-pill)] text-[var(--m-text)] active:bg-[var(--m-accent)]"
            style={{
              minWidth: "var(--m-touch-min)",
              minHeight: "var(--m-touch-min)",
              background: "var(--m-overlay)",
              border: "1px solid var(--m-border-strong)",
            }}
          >
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M8 5v14l11-7z" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
});

export default MobileMediaCard;
