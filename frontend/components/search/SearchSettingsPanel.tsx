// SearchModal 内的搜索源设置面板（⚙️ 按钮展开）
"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

interface SearchSource {
  name: string;
  label: string;
  type: "bt" | "pan";
  enabled: boolean;
}

export default function SearchSettingsPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [sources, setSources] = useState<SearchSource[]>([]);
  const [loading, setLoading] = useState(false);

  const loadSources = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api.getSearchSources();
      setSources(d.sources || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { if (open) loadSources(); }, [open, loadSources]);

  const toggleSource = async (name: string, enabled: boolean) => {
    setSources(prev => prev.map(s => s.name === name ? { ...s, enabled } : s));
    try {
      await api.toggleSearchSource(name, enabled);
    } catch {
      setSources(prev => prev.map(s => s.name === name ? { ...s, enabled: !enabled } : s));
    }
  };

  if (!open) return null;

  const btSources = sources.filter(s => s.type === "bt");
  const panSources = sources.filter(s => s.type === "pan");

  return (
    <div className="fixed top-0 left-0 w-full h-full z-[60]" onClick={onClose}>
      <div className="absolute top-16 right-16 w-72 bg-[#1a1a1a] border border-white/[0.08] rounded-xl shadow-2xl p-4 space-y-3"
        onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center justify-between">
        <span className="text-[12px] font-bold text-white">搜索源设置</span>
        <button onClick={onClose} className="text-slate-500 hover:text-white text-sm">✕</button>
      </div>

      {loading ? (
        <p className="text-[11px] text-slate-500 py-2">加载中...</p>
      ) : (
        <>
          <div>
            <p className="text-[10px] text-slate-500 mb-2">BT / 磁力</p>
            {btSources.map(s => (
              <SourceToggle key={s.name} source={s} onToggle={toggleSource} />
            ))}
          </div>
          <div className="border-t border-white/[0.04] pt-3">
            <p className="text-[10px] text-slate-500 mb-2">网盘资源</p>
            {panSources.map(s => (
              <SourceToggle key={s.name} source={s} onToggle={toggleSource} />
            ))}
          </div>
        </>
      )}
      </div>
    </div>
  );
}

function SourceToggle({ source, onToggle }: { source: SearchSource; onToggle: (name: string, enabled: boolean) => void }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className={`text-[11px] ${source.enabled ? "text-slate-200" : "text-slate-600"}`}>{source.label}</span>
      <button onClick={() => onToggle(source.name, !source.enabled)}
        className={`w-8 h-4 rounded-full transition-colors relative ${source.enabled ? "bg-blue-600" : "bg-white/[0.08]"}`}>
        <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${source.enabled ? "left-4" : "left-0.5"}`} />
      </button>
    </div>
  );
}
