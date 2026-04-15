// 订阅源选择组件（可复用：订阅配置面板 + 订阅列表）
"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

interface RSSSource {
  name: string;
  enabled: boolean;
}

interface SubscribeSourceSelectProps {
  /** 当前订阅选择的源（空数组=使用全局设置） */
  selectedSources: string[];
  /** 源选择变化回调 */
  onChange: (sources: string[]) => void;
  /** 紧凑模式（订阅列表中使用） */
  compact?: boolean;
}

export default function SubscribeSourceSelect({ selectedSources, onChange, compact }: SubscribeSourceSelectProps) {
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
      // 从全局切换到自定义：初始化为所有已启用的源
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

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-[11px] text-slate-500">订阅搜索源</label>
        {!useGlobal && (
          <button onClick={resetToGlobal} className="text-[10px] text-blue-400 hover:text-blue-300">恢复默认</button>
        )}
      </div>
      <div className={`flex gap-1.5 flex-wrap ${compact ? "" : ""}`}>
        {allSources.map(s => {
          const isActive = useGlobal ? s.enabled : selectedSources.includes(s.name);
          return (
            <button key={s.name} onClick={() => toggleSource(s.name)}
              className={`px-2.5 py-1 rounded-md text-[11px] transition-colors ${
                isActive ? "bg-blue-600/20 text-blue-300 border border-blue-500/30" : "bg-white/[0.04] text-slate-600 border border-transparent"
              }`}>
              {s.name}
            </button>
          );
        })}
      </div>
      {useGlobal && <p className="text-[9px] text-slate-600 mt-1">使用全局设置（点击可自定义）</p>}
    </div>
  );
}
