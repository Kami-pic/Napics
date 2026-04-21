// 发现页展开详情面板
"use client";
import { useState } from "react";
import type { DoubanHotItem } from "@/types";
import type { MediaDetail } from "./discoverUtils";
import { proxyUrl } from "./discoverUtils";
import { getRatingColor } from "@/lib/mediaColors";
import { api } from "@/lib/api";

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
  /** 跳转到本地媒体库目录 */
  onNavigateToLocal?: (folderPath: string) => void;
  /** 订阅按钮回调 */
  onSubscribe?: () => void;
  /** 是否已订阅 */
  isSubscribed?: boolean;
}

export default function ExpandDetail({
  item, detail, loading, onSearch, onClose, onRetry,
  defaultSource = "douban", showBangumiRating = false, onRefreshWithSource, onNavigateToLocal,
  onSubscribe, isSubscribed = false,
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
            {/* 原始语言名（日文/韩文等） */}
            <p className="text-xs text-slate-500 mt-0.5">
              {(d?.original_title && d.original_title !== (d?.title || item.title))
                ? d.original_title
                : item.clean_name_original || <span className="text-slate-700">原始名 —</span>}
            </p>
            {/* 英文名 */}
            <p className="text-xs text-slate-400 mt-0.5">
              {d?.english_title
                ? d.english_title
                : item.clean_name_en || <span className="text-slate-700">英文名 —</span>}
            </p>
          </div>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {/* 数据源下拉 + 刷新按钮 */}
            <select value={selectedSource} onChange={(e) => setSelectedSource(e.target.value as any)}
              className="bg-[#1a1a1a] border border-white/[0.06] rounded px-1.5 py-1 text-[10px] text-slate-400 outline-none focus:border-blue-500/50">
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
          <NoDetailFallback item={item} onSearch={onSearch} onRetry={handleRefresh} onSubscribe={onSubscribe} isSubscribed={isSubscribed} />
        ) : (
          <DetailContent item={item} d={d} onSearch={onSearch} showBangumiRating={showBangumiRating} onNavigateToLocal={onNavigateToLocal} onSubscribe={onSubscribe} isSubscribed={isSubscribed} />
        )}
      </div>
    </div>
  );
}


// ── 无详情时的 fallback 展示 ──
function NoDetailFallback({ item, onSearch, onRetry, onSubscribe, isSubscribed }: { item: DoubanHotItem; onSearch: () => void; onRetry: () => void; onSubscribe?: () => void; isSubscribed?: boolean }) {
  const [localSubscribed, setLocalSubscribed] = useState(false);
  const [showCandidates, setShowCandidates] = useState(false);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [candidateLoading, setCandidateLoading] = useState(false);
  const [selectedDetail, setSelectedDetail] = useState<MediaDetail | null>(null);
  const subscribed = isSubscribed || localSubscribed;

  const searchCandidates = async () => {
    setShowCandidates(true);
    setCandidateLoading(true);
    try {
      const name = item.title || "";
      const [tmdb, douban] = await Promise.allSettled([
        api.scrapeCandidates(name),
        api.scrapeDoubanCandidates(name),
      ]);
      const all: any[] = [];
      if (tmdb.status === "fulfilled") {
        (tmdb.value.candidates || []).forEach((c: any) => all.push({ ...c, _src: "tmdb" }));
      }
      if (douban.status === "fulfilled") {
        (douban.value.candidates || []).slice(0, 5).forEach((c: any) => all.push({ ...c, _src: "douban" }));
      }
      setCandidates(all);
    } catch { setCandidates([]); }
    setCandidateLoading(false);
  };

  const selectCandidate = async (c: any) => {
    const detail: MediaDetail = {
      found: true,
      tmdb_id: c.tmdb_id || 0,
      title: c.title || c.name || "",
      original_title: c.original_title || "",
      year: c.year || c.release_date?.slice(0, 4) || c.first_air_date?.slice(0, 4) || "",
      poster_url: c.poster_url || "",
      overview: c.overview || "",
      rating: c.vote_average || c.rating || 0,
      genres: c.genres || [],
      source: c._src === "douban" ? "douban" : "tmdb",
      ratings: c._src === "douban" ? { douban: c.rating || 0 } : { tmdb: c.vote_average || 0 },
    };
    setSelectedDetail(detail);
    setShowCandidates(false);
  };

  if (selectedDetail) {
    return <DetailContent item={item} d={selectedDetail} onSearch={onSearch} onSubscribe={onSubscribe} isSubscribed={isSubscribed} />;
  }

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
        <button onClick={searchCandidates} className="px-4 py-2 bg-amber-500/20 hover:bg-amber-500/30 rounded-lg text-xs font-medium text-amber-400 transition-colors">重新匹配</button>
        {onSubscribe && (
          <button onClick={() => { onSubscribe(); setLocalSubscribed(true); }} disabled={subscribed}
            className={`px-4 py-2 rounded-lg text-xs font-medium transition-colors ${
              subscribed ? "bg-emerald-600/60 text-emerald-200 cursor-default" : "bg-amber-600 hover:bg-amber-500 text-white"
            }`}>
            {subscribed ? "📌 已订阅" : "📌 订阅"}
          </button>
        )}
        {item.douban_id && (
          <a href={`https://movie.douban.com/subject/${item.douban_id}/`} target="_blank" rel="noopener noreferrer"
            className="px-4 py-2 bg-white/[0.06] hover:bg-white/10 rounded-lg text-xs text-slate-300 transition-colors">豆瓣</a>
        )}
      </div>
      {/* 候选列表 */}
      {showCandidates && (
        <div className="mt-3 border border-white/[0.06] rounded-lg p-3 bg-[#141414]">
          {candidateLoading ? (
            <div className="flex items-center gap-2 py-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500" />
              <span className="text-xs text-slate-500">搜索候选...</span>
            </div>
          ) : candidates.length === 0 ? (
            <p className="text-xs text-slate-600 py-2">未找到候选</p>
          ) : (
            <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
              {candidates.map((c, i) => (
                <button key={i} onClick={() => selectCandidate(c)}
                  className="w-full flex gap-2.5 p-2 rounded-lg text-left bg-white/[0.03] hover:bg-white/[0.06] border border-transparent hover:border-white/[0.08] transition-all">
                  {(c.poster_url || c.poster_path) && (
                    <img src={proxyUrl(c.poster_url || `https://image.tmdb.org/t/p/w92${c.poster_path}`)} alt="" className="w-8 h-12 rounded object-cover flex-shrink-0" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-slate-200 truncate">{c.title || c.name}</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className={`text-[10px] px-1 py-0.5 rounded ${c._src === "douban" ? "bg-green-500/10 text-green-400" : "bg-blue-500/10 text-blue-400"}`}>
                        {c._src === "douban" ? "豆瓣" : "TMDB"}
                      </span>
                      {(c.year || c.release_date || c.first_air_date) && (
                        <span className="text-[10px] text-slate-500">{c.year || (c.release_date || c.first_air_date || "").slice(0, 4)}</span>
                      )}
                      {(c.vote_average || c.rating) > 0 && (
                        <span className="text-[10px] text-slate-400">⭐{c.vote_average || c.rating}</span>
                      )}
                      {c.media_type && <span className="text-[10px] text-slate-600">{c.media_type === "movie" ? "电影" : "剧集"}</span>}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
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
function DetailContent({ item, d, onSearch, showBangumiRating = false, onNavigateToLocal, onSubscribe, isSubscribed }: {
  item: DoubanHotItem; d: MediaDetail; onSearch: () => void; showBangumiRating?: boolean; onNavigateToLocal?: (folderPath: string) => void;
  onSubscribe?: () => void; isSubscribed?: boolean;
}) {
  const [localSubscribed, setLocalSubscribed] = useState(false);
  const subscribed = isSubscribed || localSubscribed;
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
      <div className="flex items-center gap-2 mt-4 flex-wrap">
        <button onClick={onSearch} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs font-medium text-white transition-colors">搜索资源</button>
        {/* 订阅按钮 */}
        {onSubscribe && (
          <button onClick={() => { onSubscribe(); setLocalSubscribed(true); }} disabled={subscribed}
            className={`px-4 py-2 rounded-lg text-xs font-medium transition-colors ${
              subscribed ? "bg-emerald-600/60 text-emerald-200 cursor-default" : "bg-amber-600 hover:bg-amber-500 text-white"
            }`}>
            {subscribed ? "📌 已订阅" : "📌 订阅"}
          </button>
        )}
        {/* 本地媒体库跳转 */}
        {item.local_status && item.local_status !== "none" && item.local_folder && onNavigateToLocal && (
          <button onClick={() => onNavigateToLocal(item.local_folder!)}
            className={`px-4 py-2 rounded-lg text-xs font-medium transition-colors ${
              item.local_status === "owned_high"
                ? "bg-emerald-600/80 hover:bg-emerald-500 text-white"
                : "bg-amber-600/80 hover:bg-amber-500 text-white"
            }`}>
            {item.local_status === "owned_high" ? "✓ 查看本地" : "↑ 查看本地"}
          </button>
        )}
        {/* 豆瓣 */}
        {(() => {
          const searchName = d.title || item.title;
          const exact = !!(item.douban_id && d.source !== "bangumi");
          const cls = exact ? "px-3 py-2 bg-white/[0.06] hover:bg-white/10 rounded-lg text-xs text-slate-300 transition-colors"
            : "px-3 py-2 bg-white/[0.03] hover:bg-white/[0.06] rounded-lg text-xs text-slate-500 transition-colors";
          const href = exact ? `https://movie.douban.com/subject/${item.douban_id}/`
            : `https://search.douban.com/movie/subject_search?search_text=${encodeURIComponent(searchName)}`;
          return <a href={href} target="_blank" rel="noopener noreferrer" className={cls}>豆瓣</a>;
        })()}
        {/* TMDB */}
        {(() => {
          const tid = d.external_ids?.tmdb_id || d.tmdb_id;
          const searchName = d.original_title || d.title || item.title;
          const exact = !!(tid && tid > 0);
          const cls = exact ? "px-3 py-2 bg-white/[0.06] hover:bg-white/10 rounded-lg text-xs text-slate-300 transition-colors"
            : "px-3 py-2 bg-white/[0.03] hover:bg-white/[0.06] rounded-lg text-xs text-slate-500 transition-colors";
          const mediaPath = d.total_seasons || d.episode_count ? "tv" : "movie";
          const href = exact ? `https://www.themoviedb.org/${mediaPath}/${tid}`
            : `https://www.themoviedb.org/search?query=${encodeURIComponent(searchName)}`;
          return <a href={href} target="_blank" rel="noopener noreferrer" className={cls}>TMDB</a>;
        })()}
        {/* IMDB */}
        {(() => {
          const imdbId = d.external_ids?.imdb_id || d.imdb_id;
          const searchName = d.original_title || d.title || item.title;
          const exact = !!imdbId;
          const cls = exact ? "px-3 py-2 bg-white/[0.06] hover:bg-white/10 rounded-lg text-xs text-slate-300 transition-colors"
            : "px-3 py-2 bg-white/[0.03] hover:bg-white/[0.06] rounded-lg text-xs text-slate-500 transition-colors";
          const href = exact ? `https://www.imdb.com/title/${imdbId}`
            : `https://www.imdb.com/find/?q=${encodeURIComponent(searchName)}`;
          return <a href={href} target="_blank" rel="noopener noreferrer" className={cls}>IMDB</a>;
        })()}
        {/* Bangumi */}
        {(() => {
          const searchName = item.subtitle || d.original_title || d.title || item.title;
          const exact = !!(item.douban_id && (d.source === "bangumi" || showBangumiRating));
          const cls = exact ? "px-3 py-2 bg-white/[0.06] hover:bg-white/10 rounded-lg text-xs text-slate-300 transition-colors"
            : "px-3 py-2 bg-white/[0.03] hover:bg-white/[0.06] rounded-lg text-xs text-slate-500 transition-colors";
          const href = exact ? `https://bgm.tv/subject/${item.douban_id}`
            : `https://bgm.tv/subject_search/${encodeURIComponent(searchName)}`;
          return <a href={href} target="_blank" rel="noopener noreferrer" className={cls}>Bangumi</a>;
        })()}
        {/* 数据来源标签 */}
        <span className="text-[10px] text-slate-600 ml-auto">数据来自 {sourceLabel}</span>
      </div>
    </>
  );
}
