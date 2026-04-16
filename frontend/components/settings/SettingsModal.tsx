// 设置弹窗
"use client";
import { useState, useEffect } from "react";
import type { AppConfig } from "@/types";

interface SettingsModalProps {
  open: boolean; onClose: () => void;
  config: AppConfig; onSave: (c: AppConfig) => void; setConfig: (c: AppConfig) => void;
  paths: string[]; setPaths: (p: string[]) => void;
}

// 按分组定义字段，group 用于插入分割线
const FIELD_GROUPS: { group: string; fields: { label: string; key: string; desc: string; link?: boolean; type?: string }[] }[] = [
  { group: "影视数据", fields: [
    { label: "TMDB API Key", key: "tmdb_api_key", desc: "影视封面和标准化标题" },
    { label: "HTTP 代理", key: "http_proxy", desc: "如 http://127.0.0.1:7890，留空不使用代理" },
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
    { label: "Alist 地址", key: "alist_url", desc: "网盘转存", link: true },
    { label: "Alist Token", key: "alist_token", desc: "管理后台 → 生成 Token" },
  ]},
  { group: "AI 辅助", fields: [
    { label: "AI Base URL", key: "openai_base_url", desc: "如 https://api.openai.com/v1" },
    { label: "AI API Key", key: "openai_api_key", desc: "LLM 接口密钥" },
    { label: "AI 模型", key: "openai_model", desc: "如 gpt-4o / deepseek-chat" },
  ]},
];

export default function SettingsModal({ open, onClose, config, onSave, setConfig, paths, setPaths }: SettingsModalProps) {
  const [cacheInfo, setCacheInfo] = useState<{ size_mb: number; file_count: number } | null>(null);
  useEffect(() => {
    if (open) fetch("http://localhost:8000/cache/info").then(r => r.json()).then(setCacheInfo).catch(() => {});
  }, [open]);

  if (!open) return null;
  const updatePath = (i: number, v: string) => { const n = [...paths]; n[i] = v; setPaths(n); };

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
          {/* NAS 扫描路径 */}
          <div className="pb-3">
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
          {/* 排除文件夹（紧跟路径下面）*/}
          <div className="pb-3 border-b border-white/[0.06]">
            <label className="text-sm font-medium text-slate-300">排除文件夹</label>
            <textarea rows={2} value={(config.exclude_dirs || "").split(",").join("\n")}
              onChange={e => setConfig({ ...config, exclude_dirs: e.target.value.split("\n").join(",") })}
              className="w-full mt-1.5 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm font-mono text-slate-300 outline-none focus:border-blue-500/30" placeholder="@eaDir&#10;#recycle" />
          </div>

          {/* 按分组渲染字段 */}
          {FIELD_GROUPS.map((g, gi) => (
            <div key={g.group} className={gi > 0 ? "pt-3 border-t border-white/[0.06]" : ""}>
              {g.fields.map(f => {
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
              })}
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
          {/* 影子名 */}
          <div className="pt-3 border-t border-white/[0.06]">
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-slate-300">影子名管理</label>
                <p className="text-xs text-slate-600 mt-0.5">从 NFO 批量提取英文原名作为影子名</p>
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
                <input value={config.recycle_bin_path || ""} onChange={(e) => setConfig({ ...config, recycle_bin_path: e.target.value })}
                  placeholder="如 \\\\DS218play\\share\\回收站"
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
