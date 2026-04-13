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
          <span className={`absolute top-0 left-0 w-8 h-8 flex items-center justify-center text-sm font-black rounded-br-lg ${
            index < 3 ? "bg-yellow-500/90 text-black" : "bg-black/70 text-white/80"
          }`}>
            {index + 1}
          </span>
        )}
        {/* 右上角评分 */}
        <span className={`absolute top-3 right-3 bg-black/80 px-2 py-0.5 rounded-lg text-sm font-extrabold ${hasRating ? ratingColor : "text-slate-500"}`}>
          {hasRating ? item.rating : "—"}
        </span>
        {/* 本地媒体库状态角标 */}
        {localStatus === "owned_high" && (
          <span className={`absolute ${showRank ? "top-10" : "top-3"} left-3 bg-emerald-600/90 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-md leading-none flex items-center gap-0.5`}>
            ✓ 已有
          </span>
        )}
        {localStatus === "owned_low" && (
          <span className={`absolute ${showRank ? "top-10" : "top-3"} left-3 bg-amber-600/90 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-md leading-none flex items-center gap-0.5`}>
            ↑ 可升级
          </span>
        )}
        {/* 订阅角标 */}
        {isSubscribed && !localStatus?.startsWith("owned") && (
          <span className={`absolute ${showRank ? "top-10" : "top-3"} left-3 bg-violet-600/90 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-md leading-none`}>
            📌
          </span>
        )}
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
          <p className="text-[11px] text-slate-400 mt-1 truncate">{meta.join(" · ") || "—"}</p>
        </div>
      </div>
    </div>
  );
});

export default DiscoverCard;
