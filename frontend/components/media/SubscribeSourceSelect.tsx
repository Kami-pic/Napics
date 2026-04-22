// 订阅源选择组件：RSS/直搜分组展示 + 内容类型推荐
"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

interface RSSSource {
  name: string;
  enabled: boolean;
}

// RSS 源集合（高频轮询）
const RSS_SOURCES = new Set(["prowlarr", "mikan", "nyaa", "eztv", "acgrip", "bangumi_moe", "yts", "dmhy"]);

// 内容类型推荐
const RECOMMENDATIONS: Record<string, { rss: string[]; search: string[]; tip: string }> = {
  anime: { rss: ["mikan", "nyaa", "acgrip"], search: [], tip: "动画推荐：蜜柑+Nyaa+ACG.RIP" },
  us_tv: { rss: ["eztv", "prowlarr"], search: ["prowlarr"], tip: "美剧推荐：EZTV+Prowlarr" },
  cn_tv: { rss: [], search: ["cilixiong", "xl720"], tip: "国产剧推荐：磁力熊+XL720" },
  movie: { rss: ["yts", "prowlarr"], search: ["prowlarr", "cilixiong"], tip: "电影推荐：YTS+Prowlarr" },
};

interface SubscribeSourceSelectProps {
  selectedSources: string[];
  onChange: (sources: string[]) => void;
  compact?: boolean;
  mediaType?: string;
}

export default function SubscribeSourceSelect({ selectedSources, onChange, compact, mediaType }: SubscribeSourceSelectProps) {
  const [allSources, setAllSources] = useState<RSSSource[]>([]);
  const [loading, setLoading] = useState(false);
  const useGlobal = selectedSources.length === 0;

  const loadSources = useCallback(async () => {
    setLoading(true);
    try {
      const data: any = await api.getSubscriptionSources();
      setAllSources(Array.isArray(data) ? data : data.sources || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadSources(); }, [loadSources]);

  const toggleSource = (name: string) => {
    if (useGlobal) {
      const enabledNames = allSources.filter(s => s.enabled).map(s => s.name);
      const next = enabledNames.includes(name)
        ? enabledNames.filter(n => n !== name)
        : [...enabledNames, name];
      onChange(next);
    } else {
      const next = selectedSources.includes(name)
        ? selectedSources.filter(n => n !== name)
        : [...selectedSources, name];
      onChange(next);
    }
  };

  const resetToGlobal = () => onChange([]);

  if (loading) return <p className="text-[10px] text-slate-600">加载源...</p>;
  if (allSources.length === 0) return null;

  // 分组：RSS 源 vs 直搜源
  const rssSources = allSources.filter(s => RSS_SOURCES.has(s.name));
  const searchSources = allSources.filter(s => !RSS_SOURCES.has(s.name));

  // 推荐提示
  const rec = mediaType === "tv" ? RECOMMENDATIONS.us_tv : RECOMMENDATIONS.movie;
  const recommendedNames = new Set([...(rec?.rss || []), ...(rec?.search || [])]);

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-[11px] text-slate-500">订阅搜索源</label>
        {!useGlobal && (
          <button onClick={resetToGlobal} className="text-[10px] text-blue-400 hover:text-blue-300">恢复默认</button>
        )}
      </div>

      {/* RSS 源组 */}
      {rssSources.length > 0 && (
        <div className="mb-2">
          <p className="text-[10px] text-slate-600 mb-1">RSS 源（每 15-30 分钟自动检查）</p>
          <div className="flex gap-1.5 flex-wrap">
            {rssSources.map(s => {
              const isActive = useGlobal ? s.enabled : selectedSources.includes(s.name);
              const isRecommended = recommendedNames.has(s.name);
              return (
                <button key={s.name} onClick={() => toggleSource(s.name)}
                  className={`px-2.5 py-1 rounded-md text-[11px] transition-colors ${
                    isActive
                      ? "bg-blue-600/20 text-blue-300 border border-blue-500/30"
                      : "bg-white/[0.04] text-slate-600 border border-transparent"
                  } ${isRecommended && !isActive ? "ring-1 ring-amber-500/30" : ""}`}>
                  {s.name}
                  {isRecommended && !isActive && <span className="ml-0.5 text-amber-400">★</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 直搜源组 */}
      {searchSources.length > 0 && (
        <div>
          <p className="text-[10px] text-slate-600 mb-1">直搜源（每 4-12 小时搜索补充）</p>
          <div className="flex gap-1.5 flex-wrap">
            {searchSources.map(s => {
              const isActive = useGlobal ? s.enabled : selectedSources.includes(s.name);
              const isRecommended = recommendedNames.has(s.name);
              return (
                <button key={s.name} onClick={() => toggleSource(s.name)}
                  className={`px-2.5 py-1 rounded-md text-[11px] transition-colors ${
                    isActive
                      ? "bg-emerald-600/20 text-emerald-300 border border-emerald-500/30"
                      : "bg-white/[0.04] text-slate-600 border border-transparent"
                  } ${isRecommended && !isActive ? "ring-1 ring-amber-500/30" : ""}`}>
                  {s.name}
                  {isRecommended && !isActive && <span className="ml-0.5 text-amber-400">★</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {useGlobal && <p className="text-[9px] text-slate-600 mt-1">使用全局设置（点击可自定义）</p>}
      {rec?.tip && <p className="text-[9px] text-amber-400/60 mt-1">💡 {rec.tip}</p>}
    </div>
  );
}
