// 发现页展开详情面板
"use client";
import { useState } from "react";
import type { DoubanHotItem } from "@/types";
import type { MediaDetail } from "./discoverUtils";
import { proxyUrl } from "./discoverUtils";
import { getRatingColor } from "@/lib/mediaColors";

const SOURCE_OPTIONS = [
  { value: "douban", label: "豆瓣" },
  { value: "tmdb", label: "TMDB" },
  { value: "bangumi", label: "Bangumi" },
];

export interface ExpandDetailProps {
  item: DoubanHotItem;
  detail: MediaDetail | null;
  loading: boolean;
  onSearch: () => void;
  onClose: () => void;
  onRetry: () => void;
  /** 当前 tab 的默认数据源 */
  defaultSource?: "douban" | "tmdb" | "bangumi";
  /** 是否显示 Bangumi 评分（热门动画 + Bangumi 趋势 tab） */
  showBangumiRating?: boolean;
  /** 切换数据源刷新（清缓存+重新请求） */
  onRefreshWithSource?: (source: string) => void;
}

export default function ExpandDetail({
  item, detail, loading, onSearch, onClose, onRetry,
  defaultSource = "douban", showBangumiRating = false, onRefreshWithSource,
}: ExpandDetailProps) {
  const d = detail?.found ? detail : null;
  const detailPoster = d?.poster_url ? proxyUrl(d.poster_url) : "";
  const cardPoster = item.cover_url ? proxyUrl(item.cover_url) : "";
  const posterSrc = detailPoster || cardPoster;
  const [selectedSource, setSelectedSource] = useState(defaultSource);

  const handleRefresh = () => {
    if (onRefreshWithSource) onRefreshWithSource(selectedSource);
  };

  return (
    <div className="flex gap-5">
      {/* 海报 */}
      <div className="w-[140px] flex-shrink-0">
        <div className="aspect-[2/3] bg-[#1a1a1a] rounded-lg overflow-hidden">
          {posterSrc ? (
            <img key={item.douban_id || item.title} src={posterSrc} alt={item.title}
              className="w-full h-full object-cover"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-slate-700 text-xs">暂无封面</div>
          )}
        </div>
      </div>
      {/* 信息区 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-white">{d?.title || item.title}</h3>
            {(d?.original_title && d.original_title !== d.title) && (
              <p className="text-xs text-slate-500 mt-0.5">{d.original_title}</p>
            )}
          </div>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {/* 数据源下拉 + 刷新按钮 */}
            <select value={selectedSource} onChange={(e) => setSelectedSource(e.target.value as any)}
              className="bg-white/[0.04] border border-white/[0.06] rounded px-1.5 py-1 text-[10px] text-slate-400 outline-none focus:border-blue-500/50">
              {SOURCE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <button onClick={handleRefresh} disabled={loading}
              className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-blue-400 hover:bg-blue-500/10 transition-all disabled:opacity-30"
              title="刷新详情">
              <svg className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
            <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all">✕</button>
          </div>
        </div>
        {loading ? (
          <div className="flex items-center gap-2 py-8">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500" />
            <span className="text-xs text-slate-500">加载详情...</span>
          </div>
        ) : !d ? (
          <NoDetailFallback item={item} onSearch={onSearch} onRetry={handleRefresh} />
        ) : (
          <DetailContent item={item} d={d} onSearch={onSearch} showBangumiRating={showBangumiRating} />
        )}
      </div>
    </div>
  );
}


// ── 无详情时的 fallback 展示 ──
function NoDetailFallback({ item, onSearch, onRetry }: { item: DoubanHotItem; onSearch: () => void; onRetry: () => void }) {
  return (
    <div className="mt-3">
      <div className="flex items-center gap-2 flex-wrap">
        {item.year && <span className="text-xs text-slate-400 bg-white/[0.06] px-2 py-0.5 rounded">{item.year}</span>}
        {item.rating > 0 && <span className={`text-xs ${getRatingColor("douban")} bg-green-400/10 px-2 py-0.5 rounded font-bold`}>⭐{item.rating}</span>}
        {!item.rating && <span className="text-xs text-slate-500 bg-white/[0.06] px-2 py-0.5 rounded">暂无评分</span>}
        {item.episode && <span className="text-xs text-slate-500">{item.episode}</span>}
      </div>
      <p className="text-xs text-slate-500 mt-4">暂无相关数据 <button onClick={onRetry} className="text-blue-400 hover:text-blue-300 ml-2">重试</button></p>
      <div className="flex gap-2 mt-4">
        <button onClick={onSearch} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs font-medium text-white transition-colors">搜索资源</button>
        {item.douban_id && (
          <a href={`https://movie.douban.com/subject/${item.douban_id}/`} target="_blank" rel="noopener noreferrer"
            className="px-4 py-2 bg-white/[0.06] hover:bg-white/10 rounded-lg text-xs text-slate-300 transition-colors">豆瓣</a>
        )}
      </div>
    </div>
  );
}

// ── 星星 SVG ──
function StarIcon() {
  return (
    <svg className="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
    </svg>
  );
}

// ── 有详情时的完整展示 ──
function DetailContent({ item, d, onSearch, showBangumiRating = false }: {
  item: DoubanHotItem; d: MediaDetail; onSearch: () => void; showBangumiRating?: boolean;
}) {
  const ratings = d.ratings || {};
  const doubanRating = ratings.douban || 0;
  const tmdbRating = ratings.tmdb || 0;
  const bangumiRating = ratings.bangumi || 0;
  const hasAnyRating = doubanRating > 0 || tmdbRating > 0 || bangumiRating > 0;
  const detailSource = d.source || "tmdb";
  const sourceLabel = detailSource === "douban" ? "豆瓣" : detailSource === "bangumi" ? "Bangumi" : "TMDB";

  return (
    <>
      <div className="flex items-center gap-2 mt-3 flex-wrap">
        <span className="text-xs text-slate-400 bg-white/[0.06] px-2 py-0.5 rounded">{d.year || item.year || "—"}</span>
        {/* 豆瓣评分 */}
        {doubanRating > 0 && (
          <span className={`text-xs ${getRatingColor("douban")} bg-green-400/10 px-2 py-0.5 rounded font-bold flex items-center gap-0.5`}>
            <StarIcon /> 豆瓣 {doubanRating}
          </span>
        )}
        {/* TMDB 评分 */}
        {tmdbRating > 0 && (
          <span className={`text-xs ${getRatingColor("tmdb")} bg-blue-400/10 px-2 py-0.5 rounded font-bold flex items-center gap-0.5`}>
            <StarIcon /> TMDB {tmdbRating}
          </span>
        )}
        {/* Bangumi 评分（仅热门动画 + Bangumi 趋势 tab 显示） */}
        {showBangumiRating && bangumiRating > 0 && (
          <span className={`text-xs ${getRatingColor("bangumi")} bg-pink-400/10 px-2 py-0.5 rounded font-bold flex items-center gap-0.5`}>
            <StarIcon /> Bangumi {bangumiRating}
          </span>
        )}
        {!hasAnyRating && !item.rating && <span className="text-xs text-slate-500 bg-white/[0.06] px-2 py-0.5 rounded">暂无评分</span>}
        {d.runtime ? <span className="text-xs text-slate-500">{d.runtime} 分钟</span> : null}
        {d.total_seasons ? <span className="text-xs text-slate-500">{d.total_seasons} 季</span> : null}
        {d.episode_count ? <span className="text-xs text-slate-500">{d.episode_count} 集</span> : null}
        {d.countries && d.countries.length > 0 && <span className="text-xs text-slate-500">{d.countries.join(" / ")}</span>}
      </div>
      {d.genres && d.genres.length > 0 && (
        <div className="flex gap-1.5 mt-2 flex-wrap">
          {d.genres.map(g => (
            <span key={g} className="text-[10px] text-slate-400 border border-white/[0.08] px-1.5 py-0.5 rounded">{g}</span>
          ))}
        </div>
      )}
      <p className="text-xs text-slate-400 mt-3 leading-relaxed line-clamp-3">{d.overview || "暂无简介"}</p>
      <div className="mt-3 space-y-1">
        {d.director && <p className="text-xs text-slate-500">导演：<span className="text-slate-300">{d.director}</span></p>}
        {d.cast && d.cast.length > 0 && <p className="text-xs text-slate-500">主演：<span className="text-slate-300">{d.cast.join(" / ")}</span></p>}
      </div>
      <div className="flex items-center gap-2 mt-4">
        <button onClick={onSearch} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs font-medium text-white transition-colors">搜索资源</button>
        {/* 豆瓣链接：仅当 item.douban_id 是真正的豆瓣 ID 时显示（Bangumi 趋势 tab 的 douban_id 实际是 bgm_id，不显示） */}
        {item.douban_id && d.source !== "bangumi" && (
          <a href={`https://movie.douban.com/subject/${item.douban_id}/`} target="_blank" rel="noopener noreferrer"
            className="px-3 py-2 bg-white/[0.06] hover:bg-white/10 rounded-lg text-xs text-slate-300 transition-colors">豆瓣</a>
        )}
        {/* TMDB 链接 */}
        {(d.external_ids?.tmdb_id || d.tmdb_id) && ((d.external_ids?.tmdb_id ?? 0) > 0 || (d.tmdb_id ?? 0) > 0) && (() => {
          const tid = d.external_ids?.tmdb_id || d.tmdb_id;
          const mediaPath = d.total_seasons || d.episode_count ? "tv" : "movie";
          return (
            <a href={`https://www.themoviedb.org/${mediaPath}/${tid}`}
              target="_blank" rel="noopener noreferrer"
              className="px-3 py-2 bg-white/[0.06] hover:bg-white/10 rounded-lg text-xs text-slate-300 transition-colors">TMDB</a>
          );
        })()}
        {/* IMDB 链接 */}
        {(d.external_ids?.imdb_id || d.imdb_id) && (
          <a href={`https://www.imdb.com/title/${d.external_ids?.imdb_id || d.imdb_id}`} target="_blank" rel="noopener noreferrer"
            className="px-3 py-2 bg-white/[0.06] hover:bg-white/10 rounded-lg text-xs text-slate-300 transition-colors">IMDB</a>
        )}
        {/* Bangumi 链接：热门动画和 Bangumi 趋势 tab */}
        {item.douban_id && (d.source === "bangumi" || showBangumiRating) && (
          <a href={`https://bgm.tv/subject/${item.douban_id}`} target="_blank" rel="noopener noreferrer"
            className="px-3 py-2 bg-white/[0.06] hover:bg-white/10 rounded-lg text-xs text-slate-300 transition-colors">Bangumi</a>
        )}
        {/* 数据来源标签 */}
        <span className="text-[10px] text-slate-600 ml-auto">数据来自 {sourceLabel}</span>
      </div>
    </>
  );
}
