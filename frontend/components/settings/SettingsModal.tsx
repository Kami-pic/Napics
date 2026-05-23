// 设置弹窗
"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useInstalledPlugins } from "@/hooks/useInstalledPlugins";
import PathInput from "./PathInput";
import { AISettingsSection } from "./AISettingsSection";
import type { AppConfig, ProviderMetadata } from "@/types";

interface SettingsModalProps {
  open: boolean; onClose: () => void;
  config: AppConfig; onSave: (c: AppConfig) => void; setConfig: (c: AppConfig) => void;
  paths: string[]; setPaths: (p: string[]) => void;
  onRefresh?: () => void;
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
    return "默认：媒体库同级隐藏目录，如 \\\\NAS\\share\\.recycle_bins\\Movies";
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

export default function SettingsModal({ open, onClose, config, onSave, setConfig, paths, setPaths, onRefresh }: SettingsModalProps) {
  const [cacheInfo, setCacheInfo] = useState<{ size_mb: number; file_count: number } | null>(null);
  const [advancedExpanded, setAdvancedExpanded] = useState(false);
  const [metadataProviders, setMetadataProviders] = useState<ProviderMetadata[]>([]);
  const [connTest, setConnTest] = useState<Record<string, "idle" | "testing" | "ok" | "fail">>({});
  const plugins = useInstalledPlugins();

  useEffect(() => {
    if (open) {
      api.getProviders()
        .then(catalog => setMetadataProviders(catalog.metadata || []))
        .catch(() => setMetadataProviders([]));
      fetch("http://localhost:8000/cache/info").then(r => r.json()).then(setCacheInfo).catch(() => {});
    }
  }, [open]);

  if (!open) return null;
  const updatePath = (i: number, v: string) => { const n = [...paths]; n[i] = v; setPaths(n); };
  const recycleBinPlaceholder = getDefaultRecycleBinPlaceholder(paths);

  const testConnection = async (key: string) => {
    setConnTest(prev => ({ ...prev, [key]: "testing" }));
    try {
      if (key === "tmdb") {
        const resp = await fetch(`https://api.themoviedb.org/3/configuration?api_key=${(config.tmdb_api_key || "").trim()}`, { signal: AbortSignal.timeout(8000) });
        setConnTest(prev => ({ ...prev, [key]: resp.ok ? "ok" : "fail" }));
      } else if (key === "prowlarr") {
        const resp = await fetch(`${(config.prowlarr_url || "").replace(/\/$/, "")}/api/v1/health?apikey=${(config.prowlarr_api_key || "").trim()}`, { signal: AbortSignal.timeout(5000) });
        setConnTest(prev => ({ ...prev, [key]: resp.ok ? "ok" : "fail" }));
      } else if (key === "qb") {
        const resp = await fetch(`${(config.qb_url || "").replace(/\/$/, "")}/api/v2/app/version`, { signal: AbortSignal.timeout(5000) });
        setConnTest(prev => ({ ...prev, [key]: resp.ok ? "ok" : "fail" }));
      } else if (key === "alist") {
        const resp = await fetch(`${(config.alist_url || "").replace(/\/$/, "")}/api/me`, { headers: { Authorization: config.alist_token || "" }, signal: AbortSignal.timeout(5000) });
        setConnTest(prev => ({ ...prev, [key]: resp.ok ? "ok" : "fail" }));
      }
    } catch {
      setConnTest(prev => ({ ...prev, [key]: "fail" }));
    }
  };

  const ConnTestBtn = ({ testKey, disabled }: { testKey: string; disabled?: boolean }) => {
    const st = connTest[testKey];
    return (
      <button onClick={() => testConnection(testKey)} disabled={disabled || st === "testing"}
        className="px-2 py-1 rounded text-[10px] bg-white/[0.04] hover:bg-white/[0.08] text-slate-500 hover:text-slate-300 disabled:opacity-40 transition-all flex-shrink-0">
        {st === "testing" ? "..." : st === "ok" ? "✓ 连接成功" : st === "fail" ? "✗ 失败" : "测试"}
      </button>
    );
  };

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
                    // 从后端获取最新 config，确保 media_libraries 状态准确
                    let latestConfig = config;
                    try { latestConfig = await api.getConfig(); } catch {}
                    const hasMediaLibraries = (latestConfig.media_libraries || []).length > 0;
                    if (remaining.length === 0 && !hasMediaLibraries) {
                      if (!confirm("删除最后一个路径将清空媒体库，确定继续？")) return;
                      try { await fetch("http://localhost:8000/library/reset", { method: "POST" }); } catch {}
                      setPaths([""]);
                      const resetConfig = { ...latestConfig, scan_paths: [] };
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
                      const newConfig = { ...latestConfig, scan_paths: newPaths.filter(x => x.trim()) };
                      await api.saveConfig(newConfig);
                      setConfig(newConfig);
                      onRefresh?.();
                    }
                  }}
                  placeholder="如 Z:\Movies 或 \\NAS\media 或 /volume1/video"
                />
              </div>
            ))}
          </div>

          {/* 媒体文件夹 */}
          <div className="pb-3 border-t border-white/[0.06] pt-3">
            <label className="text-sm font-medium text-blue-400">媒体文件夹</label>
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
                  onTagChange={async newTag => {
                    const libs = [...(config.media_libraries || [])];
                    libs[i] = { ...libs[i], category_tag: newTag };
                    const newConfig = { ...config, media_libraries: libs };
                    setConfig(newConfig);
                    await api.saveConfig(newConfig);
                    onRefresh?.();
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
                    onRefresh?.();
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
              {/* AI 辅助分组：独立组件 */}
              {g.group === "AI 辅助" ? (
                <AISettingsSection config={config} setConfig={setConfig} />
              ) : (
                /* 其他分组：正常渲染字段 */
                g.fields.map(f => {
                const val = (config as any)[f.key] || "";
                const testKeyMap: Record<string, string> = { tmdb_api_key: "tmdb", prowlarr_url: "prowlarr", qb_url: "qb", alist_url: "alist" };
                const testKey = testKeyMap[f.key];
                return (
                  <div key={f.key} className="mb-3">
                    <div className="flex items-center gap-2">
                      <label className="text-sm font-medium text-slate-300">{f.label}</label>
                      {f.link && val && <a href={val} target="_blank" rel="noopener noreferrer" className="text-[10px] text-blue-400 hover:text-blue-300">打开 ↗</a>}
                      {testKey && val && <ConnTestBtn testKey={testKey} disabled={!val.trim()} />}
                    </div>
                    <p className="text-xs text-slate-600 mt-0.5 mb-1.5">{f.desc}</p>
                    <input value={val} onChange={e => { setConfig({ ...config, [f.key]: e.target.value }); if (testKey) setConnTest(prev => ({ ...prev, [testKey]: "idle" })); }} type={f.type || "text"}
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
            <button onClick={() => setAdvancedExpanded(!advancedExpanded)}
              className="flex items-center gap-2 w-full text-left">
              <span className={`text-[10px] text-slate-600 transition-transform ${advancedExpanded ? "rotate-90" : ""}`}>▶</span>
              <label className="text-sm font-medium text-slate-400 cursor-pointer">高级设置</label>
            </button>
          </div>
          {advancedExpanded && (
          <>
          <div>
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
                <label className="text-sm font-medium text-slate-300">识别缓存</label>
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
          </>
          )}
        </div>

        <div className="mt-6 flex gap-3">
          <button onClick={() => { onSave(config); onRefresh?.(); onClose(); }} className="flex-1 bg-blue-600 hover:bg-blue-500 py-2.5 rounded-xl text-sm font-medium transition-all">保存</button>
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
