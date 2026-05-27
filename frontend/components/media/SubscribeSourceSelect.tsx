// 订阅源选择组件：RSS/直搜分组展示 + 内容类型推荐（从 provider metadata 驱动）
"use client";
import { useState, useEffect, useCallback, useMemo } from "react";
import { api } from "@/lib/api";
import type { ProviderCatalog, ProviderMetadata } from "@/types";

interface RSSSource {
  name: string;
  enabled: boolean;
}

interface SubscribeSourceSelectProps {
  selectedSources: string[];
  onChange: (sources: string[]) => void;
  compact?: boolean;
  mediaType?: string;
}

/** 从 provider capabilities 中提取 recommended_for 标签 */
function getRecommendedFor(provider: ProviderMetadata): string[] {
  return provider.capabilities
    .filter(c => c.startsWith("recommended_"))
    .map(c => c.replace("recommended_", ""));
}

/** 从 provider id 中去掉 rss_ 前缀，得到订阅系统内部源名 */
function rssIdToSourceName(id: string): string {
  return id.startsWith("rss_") ? id.slice(4) : id;
}

export default function SubscribeSourceSelect({ selectedSources, onChange, compact, mediaType }: SubscribeSourceSelectProps) {
  const [allSources, setAllSources] = useState<RSSSource[]>([]);
  const [rssProviders, setRssProviders] = useState<ProviderMetadata[]>([]);
  const [searchProviders, setSearchProviders] = useState<ProviderMetadata[]>([]);
  const [loading, setLoading] = useState(false);
  const useGlobal = selectedSources.length === 0;

  const loadSources = useCallback(async () => {
    setLoading(true);
    try {
      // 优先从 provider metadata 获取分组和推荐信息
      const catalog: ProviderCatalog = await api.getProviders();
      setRssProviders(catalog.rss || []);
      setSearchProviders(catalog.search?.filter(p => p.type === "bt") || []);

      // 仍从旧接口获取实际启用状态（保存接口兼容）
      const data: any = await api.getSubscriptionSources();
      setAllSources(Array.isArray(data) ? data : data.sources || []);
    } catch {
      // provider 接口失败时回退到旧接口
      try {
        const data: any = await api.getSubscriptionSources();
        setAllSources(Array.isArray(data) ? data : data.sources || []);
      } catch { /* ignore */ }
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadSources(); }, [loadSources]);

  // 从 provider metadata 构建 RSS 源名集合
  const rssSourceNames = useMemo(() => {
    if (rssProviders.length > 0) {
      return new Set(rssProviders.map(p => rssIdToSourceName(p.id)));
    }
    // fallback：如果 provider 接口没返回数据，用旧逻辑
    return new Set(["prowlarr", "mikan", "nyaa", "eztv", "acgrip", "bangumi_moe", "yts", "dmhy"]);
  }, [rssProviders]);

  // 从 provider metadata 构建推荐源集合
  const recommendedNames = useMemo(() => {
    const recKey = mediaType === "anime" ? "anime" : mediaType === "tv" ? "us_tv" : "movie";
    const names = new Set<string>();

    // RSS 源推荐
    for (const p of rssProviders) {
      const recs = getRecommendedFor(p);
      if (recs.includes(recKey)) {
        names.add(rssIdToSourceName(p.id));
      }
    }
    // 直搜源推荐
    for (const p of searchProviders) {
      const recs = getRecommendedFor(p);
      if (recs.includes(recKey)) {
        names.add(p.id);
      }
    }
    return names;
  }, [rssProviders, searchProviders, mediaType]);

  // 从 provider metadata 构建推荐提示文案
  const recommendTip = useMemo(() => {
    const recKey = mediaType === "anime" ? "anime" : mediaType === "tv" ? "us_tv" : "movie";
    const recNames: string[] = [];
    for (const p of rssProviders) {
      if (getRecommendedFor(p).includes(recKey)) recNames.push(p.name);
    }
    for (const p of searchProviders) {
      if (getRecommendedFor(p).includes(recKey)) recNames.push(p.name);
    }
    if (recNames.length === 0) return "";
    const typeLabel = recKey === "anime" ? "动画" : recKey === "us_tv" ? "美剧" : "电影";
    return `${typeLabel}推荐：${recNames.slice(0, 4).join("+")}`;
  }, [rssProviders, searchProviders, mediaType]);

  // 构建 provider 展示名映射
  const displayNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const p of rssProviders) map.set(rssIdToSourceName(p.id), p.name);
    for (const p of searchProviders) map.set(p.id, p.name);
    return map;
  }, [rssProviders, searchProviders]);

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
  const rssSources = allSources.filter(s => rssSourceNames.has(s.name));
  const searchSources = allSources.filter(s => !rssSourceNames.has(s.name));

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
              const isRecommended = !isActive && recommendedNames.has(s.name);
              const label = displayNameMap.get(s.name) || s.name;
              return (
                <button key={s.name} onClick={() => toggleSource(s.name)}
                  className={`px-2.5 py-1 rounded-md text-[11px] transition-colors ${
                    isActive
                      ? "bg-blue-600/30 text-blue-200 border border-blue-500/40 font-medium"
                      : "bg-white/[0.04] text-slate-600 border border-transparent hover:text-slate-400"
                  } ${isRecommended ? "ring-1 ring-amber-500/30" : ""}`}>
                  {isActive && <span className="mr-1">✓</span>}
                  {label}
                  {isRecommended && <span className="ml-0.5 text-amber-400">★</span>}
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
              const isRecommended = !isActive && recommendedNames.has(s.name);
              const label = displayNameMap.get(s.name) || s.name;
              return (
                <button key={s.name} onClick={() => toggleSource(s.name)}
                  className={`px-2.5 py-1 rounded-md text-[11px] transition-colors ${
                    isActive
                      ? "bg-emerald-600/30 text-emerald-200 border border-emerald-500/40 font-medium"
                      : "bg-white/[0.04] text-slate-600 border border-transparent hover:text-slate-400"
                  } ${isRecommended ? "ring-1 ring-amber-500/30" : ""}`}>
                  {isActive && <span className="mr-1">✓</span>}
                  {label}
                  {isRecommended && <span className="ml-0.5 text-amber-400">★</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {useGlobal && <p className="text-[9px] text-slate-600 mt-1">使用全局设置（点击可自定义）</p>}
      {recommendTip && <p className="text-[9px] text-amber-400/60 mt-1">💡 {recommendTip}</p>}
    </div>
  );
}
