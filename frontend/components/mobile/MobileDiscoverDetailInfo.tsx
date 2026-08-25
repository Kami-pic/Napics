// 发现详情的信息区：三家评分 + 规格 + 简介 + 演职员。
//
// 只列有值的字段，缺的不给占位符 —— 手机上一屏就那么高，"—" 会把真信息挤下去。
"use client";
import type { MediaDetail } from "@/components/media/discoverUtils";

const RATING_LABELS: { key: "douban" | "tmdb" | "bangumi"; label: string }[] = [
  { key: "douban", label: "豆瓣" },
  { key: "tmdb", label: "TMDB" },
  { key: "bangumi", label: "Bangumi" },
];

export interface MobileDiscoverDetailInfoProps {
  detail: MediaDetail;
}

export default function MobileDiscoverDetailInfo({ detail }: MobileDiscoverDetailInfoProps) {
  const ratings = RATING_LABELS
    .map(r => ({ ...r, value: detail.ratings?.[r.key] }))
    .filter(r => typeof r.value === "number" && r.value > 0);

  const specs: string[] = [];
  if (detail.genres?.length) specs.push(detail.genres.slice(0, 3).join(" / "));
  if (detail.countries?.length) specs.push(detail.countries.slice(0, 2).join(" / "));
  if (detail.runtime) specs.push(`${detail.runtime} 分钟`);
  if (detail.total_seasons) specs.push(`${detail.total_seasons} 季`);
  if (detail.episode_count) specs.push(`共 ${detail.episode_count} 集`);
  if (detail.status) specs.push(detail.status);

  const cast = detail.cast?.slice(0, 6).join("、") || "";

  return (
    <div className="flex flex-col gap-3">
      {ratings.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {ratings.map(r => (
            <span
              key={r.key}
              className="rounded-[var(--m-radius-sm)] px-2 py-1 text-[12px] leading-none text-[var(--m-text-muted)]"
              style={{ background: "var(--m-surface)", border: "1px solid var(--m-border)" }}
            >
              {r.label} <span className="font-semibold text-[var(--m-text)]">{r.value!.toFixed(1)}</span>
            </span>
          ))}
        </div>
      )}

      {specs.length > 0 && (
        <p className="text-[12px] text-[var(--m-text-dim)]">{specs.join(" · ")}</p>
      )}

      {detail.overview && (
        <p className="text-[13px] leading-relaxed text-[var(--m-text-muted)]">{detail.overview}</p>
      )}

      {(detail.director || cast) && (
        <dl className="flex flex-col gap-1 text-[12px]">
          {detail.director && (
            <div className="flex gap-2">
              <dt className="shrink-0 text-[var(--m-text-dim)]">导演</dt>
              <dd className="min-w-0 text-[var(--m-text-muted)]">{detail.director}</dd>
            </div>
          )}
          {cast && (
            <div className="flex gap-2">
              <dt className="shrink-0 text-[var(--m-text-dim)]">主演</dt>
              <dd className="min-w-0 text-[var(--m-text-muted)]">{cast}</dd>
            </div>
          )}
        </dl>
      )}
    </div>
  );
}
