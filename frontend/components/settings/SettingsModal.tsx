// 设置弹窗
"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useInstalledPlugins } from "@/hooks/useInstalledPlugins";
import PathInput from "./PathInput";
import type { AppConfig, AIFeaturesConfig, ProviderMetadata } from "@/types";

// AI 服务商预设
const AI_PRESETS: { label: string; base_url: string; hint: string }[] = [
  { label: "豆包", base_url: "https://ark.cn-beijing.volces.com/api/v3", hint: "模型字段填推理接入点 ID（ep-xxx 格式），需先在火山引擎控制台创建" },
  { label: "DeepSeek", base_url: "https://api.deepseek.com", hint: "模型字段填 deepseek-chat 或 deepseek-reasoner" },
  { label: "自定义", base_url: "", hint: "手动填写 Base URL" },
];

// AI 场景描述
const AI_FEATURE_LIST: { key: keyof AIFeaturesConfig; label: string; desc: string; phase: 1 | 2 }[] = [
  { key: "extract_episode", label: "文件名智能解析", desc: "整理时自动识别乱码文件名", phase: 1 },
  { key: "scrape_candidate", label: "刮削候选匹配", desc: "批量刮削时自动选择最佳候选", phase: 1 },
  { key: "library_diagnosis", label: "媒体库诊断", desc: "AI 分析媒体库健康状况", phase: 1 },
  { key: "search_recommend", label: "搜索结果推荐", desc: "标记最值得下载的资源", phase: 2 },
  { key: "natural_search", label: "自然语言搜索", desc: "用自然语言描述想找的片", phase: 2 },
  { key: "subscribe_recommend", label: "订阅推荐", desc: "根据观影偏好推荐新片", phase: 2 },
];

interface SettingsModalProps {
  open: boolean; onClose: () => void;
  config: AppConfig; onSave: (c: AppConfig) => void; setConfig: (c: AppConfig) => void;
  paths: string[]; setPaths: (p: string[]) => void;
}

// 按分组定义字段，group 用于插入分割线
const FIELD_GROUPS: { group: string; fields: { label: string; key: string; desc: string; link?: boolean; type?: string }[] }[] = [
  { group: "影视数据", fields: [
    { label: "TMDB API Key", key: "tmdb_api_key", desc: "影视封面和标准化标题" },
    { label: "HTTP 代理", key: "http_proxy", desc: "如 http://127.0.0.1:7890，TMDB 等海外服务需要" },
  ]},
  { group: "搜索下载", fields: [
    { label: "Prowlarr 地址", key: "prowlarr_url", desc: "BT/PT 全网聚合搜索后台", link: true },
    { label: "Prowlarr API Key", key: "prowlarr_api_key", desc: "Settings → General 获取" },
  ]},
  { group: "BT 下载", fields: [
    { label: "qBittorrent 地址", key: "qb_url", desc: "触发 BT 下载", link: true },
    { label: "qBittorrent 用户名", key: "qb_username", desc: "Web UI 登录用户名" },
    { label: "qBittorrent 密码", key: "qb_password", desc: "Web UI 登录密码", type: "password" },
  ]},
  { group: "网盘转存", fields: [
    { label: "OpenList 地址", key: "alist_url", desc: "网盘转存", link: true },
    { label: "OpenList Token", key: "alist_token", desc: "管理后台 → 生成 Token" },
  ]},
  { group: "AI 辅助", fields: [] },
];

function normalizePathLike(path: string): string {
  return path.replace(/[\\/]+/g, "\\").replace(/\\$/, "");
}

function getDefaultRecycleBinPlaceholder(paths: string[]): string {
  const firstPath = normalizePathLike(paths.find((path) => path.trim()) || "");
  if (!firstPath) {
    return "默认：媒体库同级隐藏目录，如 \\\\DS218play\\share\\.recycle_bins\\Movies";
  }

  const parts = firstPath.split("\\").filter(Boolean);
  if (firstPath.startsWith("\\\\")) {
    if (parts.length >= 3) {
      const libraryName = parts[parts.length - 1];
      const parent = `\\\\${parts.slice(0, -1).join("\\")}`;
      return `默认：${parent}\\.recycle_bins\\${libraryName}`;
    }
    return `默认：${firstPath}\\.recycle_bins`;
  }

  if (parts.length >= 2) {
    const libraryName = parts[parts.length - 1];
    const parent = parts.slice(0, -1).join("\\");
    return `默认：${parent}\\.recycle_bins\\${libraryName}`;
  }

  return `默认：${firstPath}\\.recycle_bins`;
}

export default function SettingsModal({ open, onClose, config, onSave, setConfig, paths, setPaths }: SettingsModalProps) {
  const [cacheInfo, setCacheInfo] = useState<{ size_mb: number; file_count: number } | null>(null);
  const [aiTestResult, setAiTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [aiTesting, setAiTesting] = useState(false);
  const [aiUsage, setAiUsage] = useState<Record<string, { calls: number; tokens: number }>>({});
  const [aiExpanded, setAiExpanded] = useState(false);
  const [metadataProviders, setMetadataProviders] = useState<ProviderMetadata[]>([]);
  const plugins = useInstalledPlugins();

  useEffect(() => {
    if (open) {
      api.getProviders()
        .then(catalog => setMetadataProviders(catalog.metadata || []))
        .catch(() => setMetadataProviders([]));
      fetch("http://localhost:8000/cache/info").then(r => r.json()).then(setCacheInfo).catch(() => {});
      fetch("http://localhost:8000/ai/status").then(r => r.json()).then(data => {
        setAiUsage(data.usage || {});
      }).catch(() => {});
      setAiTestResult(null);
    }
  }, [open]);

  if (!open) return null;
  const updatePath = (i: number, v: string) => { const n = [...paths]; n[i] = v; setPaths(n); };
  const recycleBinPlaceholder = getDefaultRecycleBinPlaceholder(paths);

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-8 z-50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-[var(--background)] border border-white/[0.06] rounded-2xl w-full max-w-2xl p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-white">设置</h2>
          <div className="flex gap-2">
            <button onClick={async () => {
              try { const blob = await (await import("@/lib/api")).api.backup(); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = `backup_${Date.now()}.zip`; a.click(); URL.revokeObjectURL(url); } catch { alert("备份失败"); }
            }} className="px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.06] rounded-lg text-[10px] text-slate-500 hover:text-slate-300 transition-all">📦 备份</button>
            <label className="px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.06] rounded-lg text-[10px] text-slate-500 hover:text-slate-300 transition-all cursor-pointer">
              📂 恢复
              <input type="file" accept=".zip" className="hidden" onChange={async e => {
                const f = e.target.files?.[0]; if (!f) return;
                try { const r = await (await import("@/lib/api")).api.restore(f); alert("恢复成功：" + (r.restored || []).join(", ")); window.location.reload(); } catch { alert("恢复失败"); }
              }} />
            </label>
          </div>
        </div>

        <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2 no-scrollbar">
          {/* 媒体库路径 */}
          <div className="pb-3">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-blue-400">媒体库路径</label>
              <button onClick={() => setPaths(["", ...paths])} className="text-xs text-blue-400 hover:text-blue-300 flex-shrink-0">+ 添加路径</button>
            </div>
            <p className="text-xs text-slate-500 mt-1 mb-3">自动识别目录下所有文件夹和媒体类型</p>
            {paths.map((p, i) => (
              <div key={i} className="mb-2">
                <PathInput
                  value={p}
                  onChange={v => updatePath(i, v)}
                  onDelete={async () => {
                    const remaining = paths.filter((_, j) => j !== i).filter(x => x.trim());
                    if (remaining.length === 0 && !(config.media_libraries || []).length) {
                      if (!confirm("删除最后一个路径将清空媒体库，确定继续？")) return;
                      try { await fetch("http://localhost:8000/library/reset", { method: "POST" }); } catch {}
                      setPaths([""]);
                      const resetConfig = { ...config, scan_paths: [] };
                      await api.saveConfig(resetConfig);
                      setConfig(resetConfig);
                      onClose();
                      window.location.reload();
                    } else {
                      if (!confirm(`确定删除路径 "${p}" ？删除后该路径下的媒体数据也会被清除。`)) return;
                      try { await fetch("http://localhost:8000/library/remove-path", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: p }) }); } catch {}
                      const newPaths = remaining.length > 0 ? remaining : [""];
                      setPaths(newPaths);
                      // 立即保存 scan_paths 变更
                      const newConfig = { ...config, scan_paths: newPaths.filter(x => x.trim()) };
                      await api.saveConfig(newConfig);
                      setConfig(newConfig);
                    }
                  }}
                  placeholder="如 Z:\Movies 或 \\NAS\media 或 /volume1/video"
                />
              </div>
            ))}
          </div>

          {/* 媒体文件夹 */}
          <div className="pb-3 border-t border-white/[0.06] pt-3">
            <label className="text-sm font-medium text-purple-400">媒体文件夹</label>
            <p className="text-xs text-slate-500 mt-1 mb-3">带类型标签的独立文件夹，置顶显示</p>
            {(config.media_libraries || []).map((lib, i) => (
              <div key={lib.name + i} className="mb-2">
                <PathInput
                  value={lib.paths[0] || ""}
                  onChange={v => {
                    const libs = [...(config.media_libraries || [])];
                    libs[i] = { ...libs[i], paths: [v] };
                    setConfig({ ...config, media_libraries: libs });
                  }}
                  tag={lib.category_tag}
                  onTagChange={newTag => {
                    const libs = [...(config.media_libraries || [])];
                    libs[i] = { ...libs[i], category_tag: newTag };
                    setConfig({ ...config, media_libraries: libs });
                  }}
                  onDelete={async () => {
                    const libPath = lib.paths[0] || "";
                    if (!confirm(`确定删除媒体文件夹 "${lib.name}" ？该文件夹下的媒体数据也会被清除。`)) return;
                    if (libPath) {
                      try { await fetch("http://localhost:8000/library/remove-path", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: libPath }) }); } catch {}
                    }
                    const newLibs = (config.media_libraries || []).filter((_, j) => j !== i);
                    const newConfig = { ...config, media_libraries: newLibs };
                    setConfig(newConfig);
                    await api.saveConfig(newConfig);
                  }}
                  placeholder="如 Z:\Movies 或 \\NAS\media"
                />
              </div>
            ))}
            {!(config.media_libraries || []).length && (
              <p className="text-xs text-slate-600 italic">暂无，可通过首页"添加媒体文件夹"入口添加</p>
            )}
          </div>
          {/* 排除文件夹 */}
          <div className="pb-3 border-b border-white/[0.06] -mt-2">
            <label className="text-sm font-medium text-slate-300">排除文件夹</label>
            <textarea rows={1} value={(config.exclude_dirs || "").split(",").join("\n")}
              onChange={e => setConfig({ ...config, exclude_dirs: e.target.value.split("\n").join(",") })}
              className="w-full mt-1.5 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm font-mono text-slate-300 outline-none focus:border-blue-500/30 resize-y min-h-[38px]" placeholder="@eaDir&#10;#recycle" />
          </div>

          {/* 按分组渲染字段（根据插件安装状态过滤） */}
          {FIELD_GROUPS.filter(g => {
            if (g.group === "影视数据") return plugins.installed.has("metadata-tmdb");
            if (g.group === "搜索下载") return plugins.installed.has("search-prowlarr");
            if (g.group === "BT 下载") return plugins.installed.has("download-qbittorrent");
            if (g.group === "网盘转存") return plugins.installed.has("download-openlist") || plugins.installed.has("storage-openlist");
            return true; // AI 辅助始终显示
          }).map((g, gi) => (
            <div key={g.group} className={gi > 0 ? "pt-3 border-t border-white/[0.06]" : ""}>
              {/* AI 辅助分组：自定义渲染 */}
              {g.group === "AI 辅助" ? (
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <label className="text-sm font-medium text-blue-400">🤖 AI 助手</label>
                    <button onClick={() => setConfig({ ...config, ai_enabled: !config.ai_enabled })}
                      className={`relative w-10 h-5 rounded-full transition-all ${config.ai_enabled ? "bg-blue-600" : "bg-white/[0.08]"}`}>
                      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${config.ai_enabled ? "left-5.5" : "left-0.5"}`} />
                    </button>
                  </div>

                  <div className={config.ai_enabled ? "" : "opacity-40 pointer-events-none"}>
                    {/* 服务商预设 */}
                    <div className="flex gap-1.5 mb-3">
                      {AI_PRESETS.map(p => (
                        <button key={p.label} onClick={() => {
                          if (p.base_url) setConfig({ ...config, openai_base_url: p.base_url });
                        }} className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all ${
                          config.openai_base_url === p.base_url && p.base_url
                            ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                            : "bg-white/[0.04] text-slate-500 border border-white/[0.06] hover:text-slate-300"
                        }`}>{p.label}</button>
                      ))}
                    </div>

                    {/* 预设提示 */}
                    {AI_PRESETS.find(p => p.base_url === config.openai_base_url)?.hint && (
                      <p className="text-[10px] text-amber-400/70 mb-3">
                        💡 {AI_PRESETS.find(p => p.base_url === config.openai_base_url)?.hint}
                      </p>
                    )}

                    {/* API 配置字段 */}
                    {[
                      { label: "Base URL", key: "openai_base_url", placeholder: "https://api.deepseek.com" },
                      { label: "API Key", key: "openai_api_key", placeholder: "sk-xxx", type: "password" },
                      { label: "模型 / 接入点", key: "openai_model", placeholder: "deepseek-chat 或 ep-xxx" },
                    ].map(f => (
                      <div key={f.key} className="mb-2">
                        <label className="text-[10px] text-slate-500 mb-1 block">{f.label}</label>
                        <input value={(config as any)[f.key] || ""} onChange={e => setConfig({ ...config, [f.key]: e.target.value })}
                          type={f.type || "text"} placeholder={f.placeholder}
                          className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-1.5 text-xs text-slate-300 outline-none focus:border-blue-500/30 placeholder:text-slate-700" />
                      </div>
                    ))}

                    {/* 测试连接 */}
                    <div className="flex items-center gap-2 mt-3 mb-3">
                      <button onClick={async () => {
                        setAiTesting(true); setAiTestResult(null);
                        try {
                          // 先保存当前配置再测试
                          await (await import("@/lib/api")).api.saveConfig(config);
                          const r = await (await import("@/lib/api")).api.testAIConnection();
                          setAiTestResult({ success: r.success, message: r.success ? "连接成功" : (r.error || "连接失败") });
                        } catch { setAiTestResult({ success: false, message: "请求失败" }); }
                        setAiTesting(false);
                      }} disabled={aiTesting || !config.openai_api_key || !config.openai_base_url || !config.openai_model}
                        className="px-3 py-1.5 bg-white/[0.04] hover:bg-blue-500/10 hover:text-blue-400 rounded-lg text-[10px] text-slate-500 transition-all disabled:opacity-30">
                        {aiTesting ? "测试中..." : "测试连接"}
                      </button>
                      {aiTestResult && (
                        <span className={`text-[10px] ${aiTestResult.success ? "text-emerald-400" : "text-red-400"}`}>
                          {aiTestResult.success ? "✅" : "❌"} {aiTestResult.message}
                        </span>
                      )}
                    </div>

                    {/* 功能开关（折叠） */}
                    <div className="border-t border-white/[0.04] pt-3 mt-1">
                      <button onClick={() => setAiExpanded(!aiExpanded)} className="flex items-center gap-1.5 mb-2">
                        <span className={`text-[10px] text-slate-500 transition-transform ${aiExpanded ? "rotate-90" : ""}`}>▶</span>
                        <label className="text-[10px] text-slate-500 cursor-pointer">功能开关</label>
                      </button>
                      {aiExpanded && <div className="space-y-1.5">
                        {AI_FEATURE_LIST.map(f => {
                          const features = config.ai_features || { extract_episode: true, scrape_candidate: true, library_diagnosis: true, search_recommend: false, natural_search: false, subscribe_recommend: false };
                          const checked = features[f.key] ?? false;
                          return (
                            <label key={f.key} className={`flex items-center gap-2.5 py-1 px-2 rounded-lg hover:bg-white/[0.02] cursor-pointer ${f.phase === 2 ? "opacity-50" : ""}`}>
                              <input type="checkbox" checked={checked} onChange={() => {
                                setConfig({ ...config, ai_features: { ...features, [f.key]: !checked } });
                              }} className="w-3.5 h-3.5 rounded accent-blue-500" />
                              <div className="flex-1 min-w-0">
                                <span className="text-xs text-slate-300">{f.label}</span>
                                {f.phase === 2 && <span className="text-[9px] text-slate-600 ml-1.5">二期</span>}
                                <p className="text-[10px] text-slate-600 truncate">{f.desc}</p>
                              </div>
                            </label>
                          );
                        })}
                      </div>}
                    </div>

                    {/* 用量统计 */}
                    {Object.keys(aiUsage).length > 0 && (
                      <div className="border-t border-white/[0.04] pt-2 mt-3">
                        <label className="text-[10px] text-slate-600 mb-1 block">本次运行用量</label>
                        <p className="text-[10px] text-slate-500">
                          调用 {Object.values(aiUsage).reduce((s, v) => s + v.calls, 0)} 次 · 约 {Object.values(aiUsage).reduce((s, v) => s + v.tokens, 0).toLocaleString()} tokens
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                /* 其他分组：正常渲染字段 */
                g.fields.map(f => {
                const val = (config as any)[f.key] || "";
                return (
                  <div key={f.key} className="mb-3">
                    <div className="flex items-center gap-2">
                      <label className="text-sm font-medium text-slate-300">{f.label}</label>
                      {f.link && val && <a href={val} target="_blank" rel="noopener noreferrer" className="text-[10px] text-blue-400 hover:text-blue-300">打开 ↗</a>}
                    </div>
                    <p className="text-xs text-slate-600 mt-0.5 mb-1.5">{f.desc}</p>
                    <input value={val} onChange={e => setConfig({ ...config, [f.key]: e.target.value })} type={f.type || "text"}
                      className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-blue-500/30" />
                  </div>
                );
              })
              )}
              {/* 影视数据组额外：默认刮削源选择已移到缓存管理区域 */}
            </div>
          ))}

          {/* 播放器路径 */}
          <div className="pt-3 border-t border-white/[0.06]">
            <label className="text-sm font-medium text-slate-300">播放器路径</label>
            <p className="text-xs text-slate-600 mt-0.5 mb-1.5">本地视频播放器可执行文件路径</p>
            <input value={config.player_path || ""} onChange={e => setConfig({ ...config, player_path: e.target.value })}
              className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-blue-500/30" />
          </div>

          {/* 缓存管理 */}
          <div className="pt-3 border-t border-white/[0.06]">
            {/* 默认刮削源：只在有元数据插件时显示 */}
            {metadataProviders.length > 0 && (
            <div className="mb-4">
              <label className="text-sm font-medium text-slate-300">默认数据源</label>
              <p className="text-xs text-slate-600 mt-0.5 mb-1.5">自动识别影视信息时优先使用的数据源</p>
              <select value={config.default_scrape_source || "tmdb"} onChange={e => setConfig({ ...config, default_scrape_source: e.target.value })}
                className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-blue-500/30">
                {metadataProviders.map(provider => (
                  <option key={provider.id} value={provider.id}>{formatMetadataProviderOption(provider)}</option>
                ))}
              </select>
            </div>
            )}
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-slate-300">刮削缓存</label>
                <p className="text-xs text-slate-600 mt-0.5">
                  {cacheInfo ? `${cacheInfo.file_count} 个文件，${cacheInfo.size_mb} MB` : "加载中..."}
                  {cacheInfo && cacheInfo.size_mb > 100 && <span className="text-yellow-400 ml-2">⚠ 缓存较大</span>}
                </p>
              </div>
              <button onClick={async () => {
                if (!confirm("确定清空所有缓存？")) return;
                try { await fetch("http://localhost:8000/cache/clear", { method: "POST" }); setCacheInfo({ size_mb: 0, file_count: 0 }); } catch { alert("清空失败"); }
              }} className="px-3 py-1.5 bg-white/[0.04] hover:bg-red-500/10 hover:text-red-400 rounded-lg text-[10px] text-slate-500 transition-all">清空缓存</button>
            </div>
          </div>
          {/* 标准化名称 */}
          <div className="pt-3 border-t border-white/[0.06]">
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-slate-300">标准化名称管理</label>
                <p className="text-xs text-slate-600 mt-0.5">从 NFO 批量提取英文原名作为标准化名称，用于搜索匹配</p>
              </div>
              <button onClick={async () => {
                try { const r = await (await import("@/lib/api")).api.batchGenerateShadowNames(); alert(`生成 ${r.generated} 个，跳过 ${r.skipped} 个`); } catch { alert("失败"); }
              }} className="px-3 py-1.5 bg-white/[0.04] hover:bg-blue-500/10 hover:text-blue-400 rounded-lg text-[10px] text-slate-500 transition-all flex-shrink-0">批量生成</button>
            </div>
          </div>
          {/* 回收站（在滚动区内）*/}
          <div className="pt-3 border-t border-white/[0.06]">
            <label className="text-sm font-medium text-slate-300">回收站</label>
            <div className="mt-2 space-y-2">
              <div>
                <label className="text-[10px] text-slate-500 mb-1 block">路径（留空使用默认）</label>
                <p className="text-[10px] text-slate-600 mb-1.5">默认放到媒体库同卷同级的隐藏回收站目录，避免被播放器直接扫到。</p>
                <input value={config.recycle_bin_path || ""} onChange={(e) => setConfig({ ...config, recycle_bin_path: e.target.value })}
                  placeholder={recycleBinPlaceholder}
                  className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-blue-500/50 placeholder:text-slate-600" />
              </div>
              <div className="flex items-center gap-3">
                <label className="text-[10px] text-slate-500">保留天数</label>
                <input type="number" value={config.recycle_bin_retention_days ?? 30} min={1} max={365}
                  onChange={(e) => setConfig({ ...config, recycle_bin_retention_days: Number(e.target.value) })}
                  className="w-20 bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-xs text-white outline-none" />
              </div>
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

function formatMetadataProviderOption(provider: ProviderMetadata): string {
  const hints = [];
  if (provider.requires.includes("api_key")) hints.push("需 API Key");
  if (provider.supportsProxy) hints.push("可走代理");
  return hints.length > 0 ? `${provider.name}（${hints.join("，")}）` : provider.name;
}
