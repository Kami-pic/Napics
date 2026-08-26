// 发现榜单的海报卡（memo：切 tab 时上一屏的卡不该整批重渲染）。
//
// 海报只有远程一条来源，必须过 proxyUrl —— 豆瓣图床有防盗链，直连在手机上是一片破图。
"use client";
import { memo, useState } from "react";

import type { DoubanHotItem } from "@/types";
import { proxyUrl } from "@/components/media/discoverUtils";
import { resolveLocalStatusTag, type LocalStatusTone } from "@/lib/discoverStatus";

/** 语义色映射。桌面用 Tailwind 语义色，移动端统一走 --m-* 变量。
 *  `subscribe` 在移动端暂时不可达（这里不传 isSubscribed，订阅态是 Phase 4 之后的事），
 *  但 Record 要覆盖全部 tone，否则加订阅态时会漏一个分支。 */
const TONE_STYLE: Record<LocalStatusTone, { color: string; background: string }> = {
  owned: { color: "var(--m-success)", background: "var(--m-success-weak)" },
  upgrade: { color: "var(--m-warning)", background: "var(--m-warning-weak)" },
  subscribe: { color: "var(--m-violet)", background: "var(--m-violet-weak)" },
};

export interface MobileDiscoverCardProps {
  item: DoubanHotItem;
  /** 榜单里的位次，周榜这类要显示排名的才用得上 */
  index: number;
  showRank?: boolean;
  /** 混合类型榜单要标"电影/剧集"，单类型榜单标了是噪音 */
  showMediaType?: boolean;
  onOpen: (item: DoubanHotItem) => void;
}

const MobileDiscoverCard = memo(function MobileDiscoverCard({
  item, index, showRank, showMediaType, onOpen,
}: MobileDiscoverCardProps) {
  const [imgFailed, setImgFailed] = useState(false);
  const cover = item.cover_url && !imgFailed ? proxyUrl(item.cover_url) : "";
  const tag = resolveLocalStatusTag(item.local_status);
  const hasRating = item.rating > 0;
  const typeLabel = item.media_type === "tv" ? "剧集" : item.media_type === "movie" ? "电影" : "";

  const meta = [item.year, item.countries?.[0], item.episodes_info || item.episode]
    .filter(Boolean)
    .join(" · ");

  return (
    <button
      type="button"
      onClick={() => onOpen(item)}
      className="flex w-full flex-col overflow-hidden rounded-[var(--m-radius)] text-left active:opacity-80"
      style={{ background: "var(--m-surface)", border: "1px solid var(--m-border)" }}
    >
      <span
        className="relative block w-full overflow-hidden"
        style={{ aspectRatio: "2 / 3", background: "var(--m-surface-raised)" }}
      >
        {cover ? (
          // eslint-disable-next-line @next/next/no-img-element -- 走后端图片代理，不进 next/image
          <img
            src={cover}
            alt=""
            loading="lazy"
            decoding="async"
            className="h-full w-full object-cover"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <span className="flex h-full w-full items-center justify-center px-2 text-center text-[11px] leading-tight text-[var(--m-text-dim)]">
            {item.title}
          </span>
        )}
        {showRank && (
          <span
            className="absolute left-1 top-0.5 text-[16px] font-bold leading-none"
            style={{
              color: index < 3 ? "var(--m-warning)" : "var(--m-text-on-media)",
              textShadow: "0 1px 3px var(--m-overlay)",
            }}
          >
            {index + 1}
          </span>
        )}
        <span
          className="absolute right-1 top-1 rounded-[var(--m-radius-sm)] px-1 py-0.5 text-[11px] font-semibold leading-none"
          style={{
            background: "var(--m-overlay)",
            // 压在海报上，没有评分时不能用 --m-text-dim（底图亮暗不可控）
            color: hasRating ? "var(--m-warning)" : "var(--m-text-on-media)",
          }}
        >
          {hasRating ? item.rating.toFixed(1) : "—"}
        </span>
        {/* 本地状态角标压在海报左下角。三列下每格只有 ~104px，
            放进底部信息行会把片名挤成两三个字 */}
        {tag && (
          <span
            className="absolute bottom-1 left-1 whitespace-nowrap rounded-[var(--m-radius-sm)] px-1 py-0.5 text-[10px] leading-none"
            style={TONE_STYLE[tag.tone]}
          >
            {tag.text}
          </span>
        )}
      </span>

      <span className="flex min-w-0 flex-col gap-0.5 px-1.5 pb-1.5 pt-1">
        {/* 两行：片名常有「第一季」「剧场版」这类后缀，单行截断后几乎认不出 */}
        <span className="line-clamp-2 text-[12px] font-medium leading-snug text-[var(--m-text)]">
          {item.title}
        </span>
        <span className="truncate text-[10px] text-[var(--m-text-dim)]">
          {showMediaType && typeLabel ? `${typeLabel} · ${meta || "—"}` : meta || "—"}
        </span>
      </span>
    </button>
  );
});

export default MobileDiscoverCard;
