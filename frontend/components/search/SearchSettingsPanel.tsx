// 搜索设置弹窗 — 二级菜单（搜索源 / 过滤规则 / 索引器 / 排序权重）
"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { AppConfig, IndexerPriority, SortWeightsConfig } from "@/types";

interface SearchSource { name: string; label: string; type: "bt" | "pan"; enabled: boolean; }
type SettingsTab = "sources" | "filter" | "indexer" | "sort";

export default function SearchSettingsPanel({ open, onClose, searching }: {
  open: boolean; onClose: () => void; searching?: boolean;
}) {
  const [tab, setTab] = useState<SettingsTab>("sources");
  const [sources, setSources] = useState<SearchSource[]>([]);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [indexers, setIndexers] = useState<IndexerPriority[]>([]);
  const [sortWeights, setSortWeights] = useState<SortWeightsConfig>({
    title_match: 0.30, resolution_upgrade: 0.25, codec_match: 0.15,
    seeder_health: 0.15, chinese_sub: 0.10, size_reasonable: 0.05,
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [srcData, cfgData, idxData, wData] = await Promise.allSettled([
        api.getSearchSources(), api.getConfig(),
        api.getIndexerPriorities(), api.getSortWeights(),
      ]);
      if (srcData.status === "fulfilled") setSources(srcData.value.sources || []);
      if (cfgData.status === "fulfilled") setConfig(cfgData.value);
      if (idxData.status === "fulfilled") setIndexers(idxData.value);
      if (wData.status === "fulfilled") setSortWeights(wData.value);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { if (open) load(); }, [open, load]);

  const toggleSource = async (name: string, enabled: boolean) => {
    setSources(prev => prev.map(s => s.name === name ? { ...s, enabled } : s));
    try { await api.toggleSearchSource(name, enabled); }
    catch { setSources(prev => prev.map(s => s.name === name ? { ...s, enabled: !enabled } : s)); }
  };

  const saveConfig = async () => {
    if (!config) return;
    setSaving(true);
    try { await api.saveConfig(config); } catch {}
    setSaving(false);
  };

  const saveIndexers = async () => {
    setSaving(true);
    try { await api.saveIndexerPriorities(indexers); } catch {}
    setSaving(false);
  };

  const saveWeights = async () => {
    setSaving(true);
    try { await api.saveSortWeights(sortWeights); } catch {}
    setSaving(false);
  };

  if (!open) return null;

  const TABS: { key: SettingsTab; label: string }[] = [
    { key: "sources", label: "搜索源" },
    { key: "filter", label: "过滤规则" },
    { key: "indexer", label: "索引器" },
    { key: "sort", label: "排序权重" },
  ];

  return (
    <div className="fixed top-0 left-0 w-full h-full z-[60]" onClick={onClose}>
      <div className="absolute top-12 right-12 w-[420px] max-h-[85vh] bg-[#141414] border border-white/[0.08] rounded-xl shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}>
        {/* 头部 */}
        <div className="flex items-center justify-between px-4 pt-3 pb-2">
          <span className="text-[12px] font-bold text-white">搜索设置</span>
          <div className="flex items-center gap-2">
            {searching && <span className="text-[10px] text-amber-400 animate-pulse">搜索中</span>}
            <button onClick={onClose} className="text-slate-500 hover:text-white text-sm">✕</button>
          </div>
        </div>
        {/* Tab 切换 */}
        <div className="flex gap-1 px-4 pb-2">
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`text-[10px] px-2 py-1 rounded transition-colors ${tab === t.key ? "bg-blue-600/20 text-blue-400" : "text-slate-500 hover:text-slate-300"}`}>
              {t.label}
            </button>
          ))}
        </div>
        {/* 内容区 */}
        <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-3">
          {loading ? <p className="text-[11px] text-slate-500 py-4 text-center">加载中...</p> : (
            <>
              {/* ── 搜索源 ── */}
              {tab === "sources" && (
                <>
                  <Section title="BT / 磁力">
                    {sources.filter(s => s.type === "bt").map(s => (
                      <Toggle key={s.name} label={s.label} enabled={s.enabled} onChange={(v) => toggleSource(s.name, v)} />
                    ))}
                  </Section>
                  <Section title="网盘资源">
                    {sources.filter(s => s.type === "pan").map(s => (
                      <Toggle key={s.name} label={s.label} enabled={s.enabled} onChange={(v) => toggleSource(s.name, v)} />
                    ))}
                  </Section>
                </>
              )}

              {/* ── 过滤规则 ── */}
              {tab === "filter" && config && (
                <>
                  <div>
                    <label className="text-[10px] text-slate-500 mb-1 block">严格排除（命中即丢弃）</label>
                    <TagInput tags={config.search_filter?.must_exclude || ["TS", "CAM", "HDTC", "TC", "TELECINE", "HDTS"]}
                      onChange={(tags) => setConfig({ ...config, search_filter: { ...config.search_filter || { must_include: [], must_exclude: [] }, must_exclude: tags } })} />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-500 mb-1 block">必须包含（至少命中一个）</label>
                    <TagInput tags={config.search_filter?.must_include || []}
                      onChange={(tags) => setConfig({ ...config, search_filter: { ...config.search_filter || { must_include: [], must_exclude: [] }, must_include: tags } })} />
                  </div>
                  <div className="flex items-center gap-3">
                    <label className="text-[10px] text-slate-500">编码偏好</label>
                    <select value={config.preferred_codec || "x265"} onChange={(e) => setConfig({ ...config, preferred_codec: e.target.value })}
                      className="bg-[#1a1a1a] border border-white/[0.06] rounded px-2 py-1 text-xs text-white outline-none">
                      <option value="x265">x265 / HEVC</option>
                      <option value="x264">x264 / AVC</option>
                      <option value="AV1">AV1</option>
                    </select>
                  </div>
                  <button onClick={saveConfig} disabled={saving}
                    className="w-full py-1.5 bg-blue-600/20 hover:bg-blue-600/30 rounded-lg text-[11px] text-blue-400 transition-colors disabled:opacity-50">
                    {saving ? "保存中..." : "保存过滤规则"}
                  </button>
                </>
              )}

              {/* ── 索引器优先级 ── */}
              {tab === "indexer" && (
                <>
                  {indexers.length === 0 ? (
                    <p className="text-xs text-slate-600 py-2">暂无索引器配置（需要 Prowlarr 连接）</p>
                  ) : indexers.map((idx, i) => (
                    <div key={idx.name + i} className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-2.5 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Toggle label="" enabled={idx.enabled} onChange={(v) => {
                            const n = [...indexers]; n[i] = { ...n[i], enabled: v }; setIndexers(n);
                          }} compact />
                          <span className={`text-[11px] ${idx.enabled ? "text-slate-300" : "text-slate-600"}`}>{idx.name}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="text-[10px] text-slate-600">优先级</span>
                          <input type="number" min={0} max={100} value={idx.priority}
                            onChange={e => { const n = [...indexers]; n[i] = { ...n[i], priority: Math.min(100, Math.max(0, parseInt(e.target.value) || 0)) }; setIndexers(n); }}
                            className="w-12 bg-[#1a1a1a] border border-white/[0.06] rounded px-1.5 py-0.5 text-[10px] text-slate-300 text-center outline-none" />
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        {(["movie", "tv", "anime"] as const).map(t => {
                          const active = idx.preferred_types.includes(t);
                          return (
                            <button key={t} onClick={() => {
                              const n = [...indexers];
                              const types = active ? idx.preferred_types.filter(x => x !== t) : [...idx.preferred_types, t];
                              n[i] = { ...n[i], preferred_types: types as ("anime" | "movie" | "tv")[] };
                              setIndexers(n);
                            }} className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${active ? "bg-blue-500/20 text-blue-400" : "bg-white/[0.04] text-slate-600"}`}>
                              {t === "movie" ? "电影" : t === "tv" ? "剧集" : "动画"}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                  {indexers.length > 0 && (
                    <button onClick={saveIndexers} disabled={saving}
                      className="w-full py-1.5 bg-blue-600/20 hover:bg-blue-600/30 rounded-lg text-[11px] text-blue-400 transition-colors disabled:opacity-50">
                      {saving ? "保存中..." : "保存索引器设置"}
                    </button>
                  )}
                </>
              )}

              {/* ── 排序权重 ── */}
              {tab === "sort" && (
                <>
                  <p className="text-[10px] text-slate-600">自定义批量推荐的评分维度权重（总和建议 1.0）</p>
                  <div className="space-y-1.5">
                    {([
                      { key: "title_match", label: "标题匹配" },
                      { key: "resolution_upgrade", label: "分辨率提升" },
                      { key: "codec_match", label: "编码匹配" },
                      { key: "seeder_health", label: "做种健康" },
                      { key: "chinese_sub", label: "中文字幕" },
                      { key: "size_reasonable", label: "大小合理" },
                    ] as const).map(({ key, label }) => (
                      <div key={key} className="flex items-center gap-2">
                        <span className="text-[10px] text-slate-500 w-16">{label}</span>
                        <input type="number" step={0.05} min={0} max={1} value={sortWeights[key]}
                          onChange={e => setSortWeights({ ...sortWeights, [key]: parseFloat(e.target.value) || 0 })}
                          className="w-14 bg-[#1a1a1a] border border-white/[0.06] rounded px-1.5 py-0.5 text-[10px] text-slate-300 text-center outline-none" />
                      </div>
                    ))}
                  </div>
                  <p className="text-[10px] text-slate-600">总和: {Object.values(sortWeights).reduce((a, b) => a + b, 0).toFixed(2)}</p>
                  <button onClick={saveWeights} disabled={saving}
                    className="w-full py-1.5 bg-blue-600/20 hover:bg-blue-600/30 rounded-lg text-[11px] text-blue-400 transition-colors disabled:opacity-50">
                    {saving ? "保存中..." : "保存排序权重"}
                  </button>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── 子组件 ──
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] text-slate-500 mb-1.5">{title}</p>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function Toggle({ label, enabled, onChange, compact }: { label: string; enabled: boolean; onChange: (v: boolean) => void; compact?: boolean }) {
  return (
    <div className={`flex items-center justify-between ${compact ? "" : "py-1"}`}>
      {label && <span className={`text-[11px] ${enabled ? "text-slate-200" : "text-slate-600"}`}>{label}</span>}
      <button onClick={() => onChange(!enabled)}
        className={`w-8 h-4 rounded-full transition-colors relative flex-shrink-0 ${enabled ? "bg-blue-600" : "bg-white/[0.08]"}`}>
        <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${enabled ? "left-4" : "left-0.5"}`} />
      </button>
    </div>
  );
}

function TagInput({ tags, onChange }: { tags: string[]; onChange: (t: string[]) => void }) {
  const [input, setInput] = useState("");
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && input.trim()) {
      e.preventDefault();
      const newTag = input.trim().toUpperCase();
      if (!tags.includes(newTag)) onChange([...tags, newTag]);
      setInput("");
    }
    if (e.key === "Backspace" && !input && tags.length > 0) onChange(tags.slice(0, -1));
  };
  return (
    <div className="flex flex-wrap gap-1 bg-[#1a1a1a] border border-white/[0.06] rounded-lg px-2 py-1.5 min-h-[28px]">
      {tags.map((tag, i) => (
        <span key={i} className="flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-white/[0.06] text-[10px] text-slate-300">
          {tag}
          <button onClick={() => onChange(tags.filter((_, j) => j !== i))} className="text-slate-500 hover:text-red-400 text-[10px]">×</button>
        </span>
      ))}
      <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
        placeholder={tags.length === 0 ? "输入后回车..." : ""} className="flex-1 min-w-[60px] bg-transparent text-[10px] text-white outline-none placeholder:text-slate-600" />
    </div>
  );
}
