// 发现页海报卡片（memo 防止展开面板切换时重新渲染）
"use client";
import { memo, useState } from "react";
import type { DoubanHotItem } from "@/types";
import { proxyUrl } from "./discoverUtils";

export interface DiscoverCardProps {
  item: DoubanHotItem;
  index: number;
  isActive: boolean;
  showRank: boolean;
  showMediaType?: boolean;
  ratingSource?: "douban" | "tmdb" | "bangumi";
  onClick: () => void;
  style?: React.CSSProperties;
  isSubscribed?: boolean;
}

function PosterFallback({ title, failed }: { title: string; failed?: boolean }) {
  return (
    <div className="absolute inset-0 bg-[#111] flex flex-col items-center justify-center gap-1.5 pointer-events-none select-none">
      <span className="text-2xl">🎬</span>
      <span className="text-[10px] text-slate-600 text-center px-3 leading-tight truncate max-w-full">{title}</span>
      {failed && <span className="text-[9px] text-slate-700">图片加载失败</span>}
    </div>
  );
}

const DiscoverCard = memo(function DiscoverCard({ item, index, isActive, showRank, showMediaType, ratingSource = "douban", onClick, style, isSubscribed }: DiscoverCardProps) {
  const [imgError, setImgError] = useState(false);
  const genres = item.genres?.slice(0, 3) || [];
  const isTV = item.media_type === "tv";

  const meta: string[] = [];
  if (item.year) meta.push(item.year);
  if (item.countries?.length) meta.push(item.countries[0]);
  if (item.episodes_info) meta.push(item.episodes_info);
  else if (item.episode) meta.push(item.episode);

  const ratingColorMap = { douban: "text-yellow-400", tmdb: "text-blue-400", bangumi: "text-pink-400" };
  const ratingColor = ratingColorMap[ratingSource] || "text-yellow-400";
  const hasRating = item.rating > 0;
  const localStatus = item.local_status;

  // 状态标签：优先级 已有+订阅合并 > 已有 > 可升级 > 已订阅
  const statusTag = localStatus === "owned_high" && isSubscribed
    ? { text: "✓ 已有·订阅", color: "text-emerald-400 bg-emerald-500/20" }
    : localStatus === "owned_low" && isSubscribed
    ? { text: "↑ 升级·订阅", color: "text-amber-400 bg-amber-500/20" }
    : localStatus === "owned_high"
    ? { text: "✓ 已有", color: "text-emerald-400 bg-emerald-500/20" }
    : localStatus === "owned_low"
    ? { text: "↑ 可升级", color: "text-amber-400 bg-amber-500/20" }
    : isSubscribed
    ? { text: "📌 已订阅", color: "text-violet-400 bg-violet-500/20" }
    : null;

  return (
    <div data-discover-card style={style}
      className={`group rounded-xl overflow-hidden bg-[#1a1a1a] border cursor-pointer transition-all ${
        isActive ? "border-blue-500/50 ring-1 ring-blue-500/20" : "border-white/[0.06] hover:border-slate-500"
      }`}
      onClick={onClick}>
      <div className="relative aspect-[2/3] bg-[#111]">
        {item.cover_url && !imgError ? (
          <img src={proxyUrl(item.cover_url)} alt={item.title}
            loading="lazy" decoding="async"
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            onError={() => setImgError(true)} />
        ) : (
          <PosterFallback title={item.title} failed={imgError} />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-[#1a1a1a] via-transparent to-transparent" />
        {showRank && (
          <div className="absolute top-[6px] left-1">
            <span className={`inline-flex items-center justify-center min-w-[28px] text-[24px] font-bold leading-none tracking-tight drop-shadow-[0_1px_3px_rgba(0,0,0,0.6)] ${
              index < 3 ? "text-yellow-400" : "text-white/70"
            }`} style={{ fontFamily: "'Impact', 'Arial Black', 'Helvetica Neue', sans-serif", WebkitTextStroke: "0.8px rgba(0,0,0,0.15)" }}>
              {index + 1}
            </span>
          </div>
        )}
        {/* 右上角评分 */}
        <div className="absolute top-2 right-2.5">
          <span className={`bg-black/70 backdrop-blur-sm px-2.5 py-1 rounded-lg text-[15px] font-bold leading-none ${hasRating ? ratingColor : "text-slate-500"}`}>
            {hasRating ? item.rating : "—"}
          </span>
        </div>
        <div className="absolute bottom-0 left-0 right-0 p-3">
          {(genres.length > 0 || showMediaType) && (
            <div className="flex gap-1 mb-1.5">
              {showMediaType && isTV && <span className="text-[10px] text-green-400 bg-green-500/15 px-1 py-0.5 rounded leading-none">剧集</span>}
              {showMediaType && !isTV && item.media_type === "movie" && <span className="text-[10px] text-blue-400 bg-blue-500/15 px-1 py-0.5 rounded leading-none">电影</span>}
              {genres.map(g => (
                <span key={g} className="text-[10px] text-slate-200 bg-white/[0.18] px-1 py-0.5 rounded leading-none">{g}</span>
              ))}
            </div>
          )}
          <p className="text-[14px] font-semibold text-white truncate leading-tight">{item.title}</p>
          <div className="flex items-center mt-1 gap-1">
            <p className="text-[11px] text-slate-400 truncate flex-1 min-w-0">{meta.join(" · ") || "—"}</p>
            {statusTag && (
              <span className={`text-[10px] ${statusTag.color} px-1.5 py-0.5 rounded leading-none flex-shrink-0 whitespace-nowrap`}>
                {statusTag.text}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

export default DiscoverCard;
