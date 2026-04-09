// 设置弹窗
"use client";
import { useState, useEffect } from "react";
import type { AppConfig, IndexerPriority, SortWeightsConfig } from "@/types";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  config: AppConfig;
  onSave: (c: AppConfig) => void;
  setConfig: (c: AppConfig) => void;
  paths: string[];
  setPaths: (p: string[]) => void;
}

const FIELDS: { label: string; key: string; desc: string; link?: boolean; type?: string }[] = [
  { label: "Prowlarr 地址", key: "prowlarr_url", desc: "BT/PT 全网聚合搜索后台", link: true },
  { label: "Prowlarr API Key", key: "prowlarr_api_key", desc: "Settings → General 获取" },
  { label: "TMDB API Key", key: "tmdb_api_key", desc: "影视封面和标准化标题" },
  { label: "qBittorrent 地址", key: "qb_url", desc: "触发 BT 下载", link: true },
  { label: "qBittorrent 用户名", key: "qb_username", desc: "Web UI 登录用户名" },
  { label: "qBittorrent 密码", key: "qb_password", desc: "Web UI 登录密码", type: "password" },
  { label: "Alist 地址", key: "alist_url", desc: "网盘转存", link: true },
  { label: "Alist Token", key: "alist_token", desc: "管理后台 → 生成 Token" },
  { label: "播放器路径", key: "player_path", desc: "本地视频播放器可执行文件路径" },
  { label: "AI Base URL", key: "openai_base_url", desc: "如 https://api.openai.com/v1" },
  { label: "AI API Key", key: "openai_api_key", desc: "LLM 接口密钥" },
  { label: "AI 模型", key: "openai_model", desc: "如 gpt-4o / deepseek-chat" },
  { label: "HTTP 代理", key: "http_proxy", desc: "如 http://127.0.0.1:7890，留空不使用代理" },
];

export default function SettingsModal({ open, onClose, config, onSave, setConfig, paths, setPaths }: SettingsModalProps) {
  const [cacheInfo, setCacheInfo] = useState<{ size_mb: number; file_count: number } | null>(null);
  const [indexers, setIndexers] = useState<IndexerPriority[]>([]);
  const [indexerSaving, setIndexerSaving] = useState(false);
  const [sortWeights, setSortWeights] = useState<SortWeightsConfig>({
    title_match: 0.30, resolution_upgrade: 0.25, codec_match: 0.15,
    seeder_health: 0.15, chinese_sub: 0.10, size_reasonable: 0.05,
  });
  const [weightsSaving, setWeightsSaving] = useState(false);

  useEffect(() => {
    if (open) {
      fetch("http://localhost:8000/cache/info").then(r => r.json()).then(setCacheInfo).catch(() => {});
      import("@/lib/api").then(m => m.api.getIndexerPriorities()).then(setIndexers).catch(() => {});
      import("@/lib/api").then(m => m.api.getSortWeights()).then(setSortWeights).catch(() => {});
    }
  }, [open]);

  if (!open) return null;
  const updatePath = (i: number, v: string) => { const n = [...paths]; n[i] = v; setPaths(n); };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-8 z-50"
      onClick={(e) => { e.stopPropagation(); if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-[var(--background)] border border-white/[0.06] rounded-2xl w-full max-w-2xl p-6">
        {/* 顶部：标题 + 备份恢复 */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-white">设置</h2>
          <div className="flex gap-2">
            <button onClick={async () => {
              try {
                const blob = await (await import("@/lib/api")).api.backup();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a"); a.href = url; a.download = `nas_media_backup_${Date.now()}.zip`; a.click();
                URL.revokeObjectURL(url);
              } catch { alert("备份失败"); }
            }} className="px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.06] rounded-lg text-[10px] text-slate-500 hover:text-slate-300 transition-all">📦 备份</button>
            <label className="px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.06] rounded-lg text-[10px] text-slate-500 hover:text-slate-300 transition-all cursor-pointer">
              📂 恢复
              <input type="file" accept=".zip" className="hidden" onChange={async e => {
                const f = e.target.files?.[0]; if (!f) return;
                try {
                  const r = await (await import("@/lib/api")).api.restore(f);
                  alert("恢复成功：" + (r.restored || []).join(", "));
                  window.location.reload();
                } catch { alert("恢复失败"); }
              }} />
            </label>
          </div>
        </div>

        <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2 no-scrollbar">
          {/* NAS 路径 */}
          <div className="pb-4 mb-2 border-b border-white/[0.06]">
            <label className="text-sm font-medium text-blue-400">NAS 扫描路径</label>
            <p className="text-xs text-slate-500 mt-1 mb-3">添加需要扫描的媒体库目录</p>
            {paths.map((p, i) => (
              <div key={i} className="flex gap-2 mb-2">
                <input value={p} onChange={e => updatePath(i, e.target.value)} placeholder="如 Z:\Movies 或 \\NAS\media"
                  className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm font-mono text-slate-300 outline-none focus:border-blue-500/30" />
                {paths.length > 1 && <button onClick={() => setPaths(paths.filter((_, j) => j !== i))} className="text-red-400 hover:text-red-300 text-xs px-2">删除</button>}
              </div>
            ))}
            <button onClick={() => setPaths([...paths, ""])} className="text-xs text-blue-400 hover:text-blue-300">+ 添加路径</button>
          </div>

          {FIELDS.map(f => {
            const val = (config as any)[f.key] || "";
            return (
              <div key={f.key}>
                <div className="flex items-center gap-2">
                  <label className="text-sm font-medium text-slate-300">{f.label}</label>
                  {f.link && val && (
                    <a href={val} target="_blank" rel="noopener noreferrer"
                      className="text-[10px] text-blue-400 hover:text-blue-300 transition-colors">打开 ↗</a>
                  )}
                </div>
                <p className="text-xs text-slate-600 mt-0.5 mb-1.5">{f.desc}</p>
                <input value={val} onChange={e => setConfig({ ...config, [f.key]: e.target.value })}
                  type={f.type || "text"}
                  className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-blue-500/30" />
              </div>
            );
          })}
          <div>
            <label className="text-sm font-medium text-slate-300">排除文件夹</label>
            <textarea rows={2} value={(config.exclude_dirs || "").split(",").join("\n")}
              onChange={e => setConfig({ ...config, exclude_dirs: e.target.value.split("\n").join(",") })}
              className="w-full mt-1.5 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm font-mono text-slate-300 outline-none focus:border-blue-500/30" placeholder="@eaDir&#10;#recycle" />
          </div>
          {/* 缓存管理 */}
          <div className="pt-4 mt-2 border-t border-white/[0.06]">
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-slate-300">刮削缓存</label>
                <p className="text-xs text-slate-600 mt-0.5">
                  {cacheInfo ? `${cacheInfo.file_count} 个文件，${cacheInfo.size_mb} MB` : "加载中..."}
                  {cacheInfo && cacheInfo.size_mb > 100 && <span className="text-yellow-400 ml-2">⚠ 缓存较大</span>}
                </p>
              </div>
              <button onClick={async () => {
                if (!confirm("确定清空所有缓存？下次加载会重新获取数据")) return;
                try {
                  await fetch("http://localhost:8000/cache/clear", { method: "POST" });
                  setCacheInfo({ size_mb: 0, file_count: 0 });
                } catch { alert("清空失败"); }
              }} className="px-3 py-1.5 bg-white/[0.04] hover:bg-red-500/10 hover:text-red-400 rounded-lg text-[10px] text-slate-500 transition-all">清空缓存</button>
            </div>
          </div>
          {/* 批量影子名 */}
          <div className="pt-4 mt-2 border-t border-white/[0.06]">
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-slate-300">影子名管理</label>
                <p className="text-xs text-slate-600 mt-0.5">从已有 NFO 批量提取英文原名作为影子名，提升搜索匹配准确率</p>
              </div>
              <button onClick={async () => {
                try {
                  const r = await (await import("@/lib/api")).api.batchGenerateShadowNames();
                  alert(`生成 ${r.generated} 个，跳过 ${r.skipped} 个，失败 ${r.failed} 个`);
                } catch { alert("批量生成失败"); }
              }} className="px-3 py-1.5 bg-white/[0.04] hover:bg-blue-500/10 hover:text-blue-400 rounded-lg text-[10px] text-slate-500 transition-all flex-shrink-0">批量生成</button>
            </div>
          </div>
          {/* 索引器优先级 */}
          <div className="pt-4 mt-2 border-t border-white/[0.06]">
            <div className="flex items-center justify-between mb-3">
              <div>
                <label className="text-sm font-medium text-slate-300">索引器优先级</label>
                <p className="text-xs text-slate-600 mt-0.5">配置 Prowlarr 索引器的搜索优先级和偏好类型</p>
              </div>
              <button onClick={async () => {
                setIndexerSaving(true);
                try {
                  await (await import("@/lib/api")).api.saveIndexerPriorities(indexers);
                } catch { alert("保存失败"); }
                setIndexerSaving(false);
              }} disabled={indexerSaving} className="px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 rounded-lg text-[10px] text-blue-400 transition-all disabled:opacity-50">
                {indexerSaving ? "保存中..." : "保存优先级"}
              </button>
            </div>
            {indexers.length === 0 ? (
              <p className="text-xs text-slate-600 py-2">暂无索引器配置</p>
            ) : (
              <div className="space-y-2">
                {indexers.map((idx, i) => (
                  <div key={idx.name + i} className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <button onClick={() => { const n = [...indexers]; n[i] = { ...n[i], enabled: !n[i].enabled }; setIndexers(n); }}
                          className={`w-8 h-4 rounded-full transition-colors relative ${idx.enabled ? "bg-blue-500" : "bg-white/[0.1]"}`}>
                          <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${idx.enabled ? "left-4.5" : "left-0.5"}`} />
                        </button>
                        <span className={`text-sm ${idx.enabled ? "text-slate-300" : "text-slate-600"}`}>{idx.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-slate-600">优先级</span>
                        <input type="number" min={0} max={100} value={idx.priority}
                          onChange={e => { const n = [...indexers]; n[i] = { ...n[i], priority: Math.min(100, Math.max(0, parseInt(e.target.value) || 0)) }; setIndexers(n); }}
                          className="w-14 bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 text-center outline-none focus:border-blue-500/30" />
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] text-slate-600 mr-1">偏好:</span>
                      {(["movie", "tv", "anime"] as const).map(t => {
                        const active = idx.preferred_types.includes(t);
                        return (
                          <button key={t} onClick={() => {
                            const n = [...indexers];
                            const types = active ? idx.preferred_types.filter(x => x !== t) : [...idx.preferred_types, t];
                            n[i] = { ...n[i], preferred_types: types as ("anime" | "movie" | "tv")[] };
                            setIndexers(n);
                          }} className={`text-[10px] px-2 py-0.5 rounded transition-colors ${active ? "bg-blue-500/20 text-blue-400" : "bg-white/[0.04] text-slate-600 hover:text-slate-400"}`}>
                            {t === "movie" ? "电影" : t === "tv" ? "剧集" : "动画"}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          {/* ── 种子排序权重配置 ── */}
          <div className="pt-4 mt-2 border-t border-white/[0.06]">
            <div className="flex items-center justify-between mb-3">
              <div>
                <label className="text-sm font-medium text-slate-300">排序权重</label>
                <p className="text-xs text-slate-600 mt-0.5">自定义批量推荐的评分维度权重（总和建议为 1.0）</p>
              </div>
              <button onClick={async () => {
                setWeightsSaving(true);
                try {
                  await (await import("@/lib/api")).api.saveSortWeights(sortWeights);
                } catch { alert("保存失败"); }
                setWeightsSaving(false);
              }} disabled={weightsSaving} className="px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 rounded-lg text-[10px] text-blue-400 transition-all disabled:opacity-50">
                {weightsSaving ? "保存中..." : "保存权重"}
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
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
                  <input type="number" step={0.05} min={0} max={1}
                    value={sortWeights[key]}
                    onChange={e => setSortWeights({ ...sortWeights, [key]: parseFloat(e.target.value) || 0 })}
                    className="w-16 bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-slate-300 text-center outline-none focus:border-blue-500/30" />
                </div>
              ))}
            </div>
            <p className="text-[10px] text-slate-600 mt-2">
              当前总和: {Object.values(sortWeights).reduce((a, b) => a + b, 0).toFixed(2)}
            </p>
          </div>
        </div>
        {/* ── 搜索过滤规则配置 ── */}
        <div className="mt-5 border-t border-white/[0.06] pt-4">
          <h3 className="text-xs font-bold text-slate-300 mb-3">搜索过滤规则</h3>
          <div className="space-y-3">
            {/* 严格排除 */}
            <div>
              <label className="text-[10px] text-slate-500 mb-1 block">严格排除（命中即丢弃）</label>
              <TagInput
                tags={config.search_filter?.must_exclude || ["TS", "CAM", "HDTC", "TC", "TELECINE", "HDTS"]}
                onChange={(tags) => setConfig({ ...config, search_filter: { ...config.search_filter || { must_include: [], must_exclude: [] }, must_exclude: tags } })}
                placeholder="输入关键词后回车..."
              />
            </div>
            {/* 必须包含 */}
            <div>
              <label className="text-[10px] text-slate-500 mb-1 block">必须包含（至少命中一个）</label>
              <TagInput
                tags={config.search_filter?.must_include || []}
                onChange={(tags) => setConfig({ ...config, search_filter: { ...config.search_filter || { must_include: [], must_exclude: [] }, must_include: tags } })}
                placeholder="如 HEVC, x265..."
              />
            </div>
            {/* 编码偏好 */}
            <div className="flex items-center gap-3">
              <label className="text-[10px] text-slate-500">编码偏好</label>
              <select value={config.preferred_codec || "x265"}
                onChange={(e) => setConfig({ ...config, preferred_codec: e.target.value })}
                className="bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-white outline-none">
                <option value="x265">x265 / HEVC</option>
                <option value="x264">x264 / AVC</option>
                <option value="AV1">AV1</option>
              </select>
            </div>
            {/* 回收站路径 */}
            <div>
              <label className="text-[10px] text-slate-500 mb-1 block">回收站路径（留空使用默认）</label>
              <input value={config.recycle_bin_path || ""}
                onChange={(e) => setConfig({ ...config, recycle_bin_path: e.target.value })}
                placeholder="如 \\\\DS218play\\share\\回收站"
                className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-blue-500/50 placeholder:text-slate-600" />
            </div>
            {/* 回收站保留天数 */}
            <div className="flex items-center gap-3">
              <label className="text-[10px] text-slate-500">回收站保留天数</label>
              <input type="number" value={config.recycle_bin_retention_days ?? 30} min={1} max={365}
                onChange={(e) => setConfig({ ...config, recycle_bin_retention_days: Number(e.target.value) })}
                className="w-20 bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-white outline-none" />
            </div>
          </div>
        </div>

        <div className="mt-6 flex gap-3">
          <button onClick={() => { onSave(config); onClose(); }} className="flex-1 bg-blue-600 hover:bg-blue-500 py-2.5 rounded-xl text-sm font-medium transition-all">保存</button>
          <button onClick={onClose} className="flex-1 bg-white/[0.06] hover:bg-white/[0.08] py-2.5 rounded-xl text-sm text-slate-400 transition-all">取消</button>
        </div>
      </div>
    </div>
  );
}

// ── Tag 标签输入组件 ──
function TagInput({ tags, onChange, placeholder }: { tags: string[]; onChange: (t: string[]) => void; placeholder?: string }) {
  const [input, setInput] = useState("");
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && input.trim()) {
      e.preventDefault();
      const newTag = input.trim().toUpperCase();
      if (!tags.includes(newTag)) onChange([...tags, newTag]);
      setInput("");
    }
    if (e.key === "Backspace" && !input && tags.length > 0) {
      onChange(tags.slice(0, -1));
    }
  };
  return (
    <div className="flex flex-wrap gap-1.5 bg-white/[0.04] border border-white/[0.06] rounded-lg px-2 py-1.5 min-h-[32px]">
      {tags.map((tag, i) => (
        <span key={i} className="flex items-center gap-1 px-2 py-0.5 rounded bg-white/[0.06] text-[10px] text-slate-300">
          {tag}
          <button onClick={() => onChange(tags.filter((_, j) => j !== i))} className="text-slate-500 hover:text-red-400">×</button>
        </span>
      ))}
      <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
        placeholder={tags.length === 0 ? placeholder : ""} className="flex-1 min-w-[80px] bg-transparent text-xs text-white outline-none placeholder:text-slate-600" />
    </div>
  );
}
