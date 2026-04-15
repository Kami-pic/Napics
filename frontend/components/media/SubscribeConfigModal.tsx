// 订阅配置弹窗：点击订阅按钮后弹出，配置质量偏好、关键词、模式等
"use client";
import { useState } from "react";
import SubscribeSourceSelect from "./SubscribeSourceSelect";

export interface SubscribeConfig {
  quality: string;
  include: string;
  exclude: string;
  mode: "notify" | "auto";
  best_version: boolean;
  save_path: string;
  search_keyword: string;
  sources: string[];
}

export interface SubscribeConfigModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (config: SubscribeConfig) => void;
  title: string;
  mediaType: string;
  defaultSavePath?: string;
}

const QUALITY_OPTIONS = [
  { value: "2160p", label: "4K (2160p)" },
  { value: "1080p", label: "1080p" },
  { value: "720p", label: "720p" },
  { value: "", label: "不限" },
];

export default function SubscribeConfigModal({
  open, onClose, onConfirm, title, mediaType, defaultSavePath = "",
}: SubscribeConfigModalProps) {
  const [config, setConfig] = useState<SubscribeConfig>({
    quality: "1080p",
    include: "",
    exclude: "",
    mode: "notify",
    best_version: false,
    save_path: defaultSavePath,
    search_keyword: "",
    sources: [],
  });

  if (!open) return null;

  const set = (key: keyof SubscribeConfig, value: string | boolean) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[60]">
      <div className="bg-[#1a1a1a] border border-white/[0.08] rounded-2xl w-full max-w-md p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-[15px] font-bold text-white">订阅设置</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white text-lg">✕</button>
        </div>
        <p className="text-[12px] text-slate-400 -mt-2">{title} · {mediaType === "tv" ? "剧集" : "电影"}</p>

        {/* 质量偏好 */}
        <div>
          <label className="text-[11px] text-slate-500 mb-1.5 block">质量偏好</label>
          <div className="flex gap-2">
            {QUALITY_OPTIONS.map(q => (
              <button key={q.value} onClick={() => set("quality", q.value)}
                className={`px-3 py-1.5 rounded-lg text-[11px] transition-colors ${
                  config.quality === q.value ? "bg-blue-600 text-white" : "bg-white/[0.04] text-slate-400 hover:text-white"
                }`}>{q.label}</button>
            ))}
          </div>
        </div>

        {/* 模式 */}
        <div>
          <label className="text-[11px] text-slate-500 mb-1.5 block">下载模式</label>
          <div className="flex gap-2">
            <button onClick={() => set("mode", "notify")}
              className={`px-3 py-1.5 rounded-lg text-[11px] transition-colors ${
                config.mode === "notify" ? "bg-blue-600 text-white" : "bg-white/[0.04] text-slate-400 hover:text-white"
              }`}>通知（手动选择）</button>
            <button onClick={() => set("mode", "auto")}
              className={`px-3 py-1.5 rounded-lg text-[11px] transition-colors ${
                config.mode === "auto" ? "bg-blue-600 text-white" : "bg-white/[0.04] text-slate-400 hover:text-white"
              }`}>自动下载</button>
          </div>
        </div>

        {/* 自动洗版 */}
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[12px] text-slate-300">自动洗版</span>
            <p className="text-[10px] text-slate-600">找到更高质量版本时自动替换</p>
          </div>
          <button onClick={() => set("best_version", !config.best_version)}
            className={`w-10 h-5 rounded-full transition-colors relative ${config.best_version ? "bg-blue-600" : "bg-white/[0.08]"}`}>
            <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${config.best_version ? "left-5" : "left-0.5"}`} />
          </button>
        </div>

        {/* 包含关键词 */}
        <div>
          <label className="text-[11px] text-slate-500 mb-1.5 block">包含关键词（多个用空格分隔，全部匹配）</label>
          <input value={config.include} onChange={e => set("include", e.target.value)}
            placeholder="如：HEVC 中字"
            className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-blue-500/50 placeholder:text-slate-600" />
        </div>

        {/* 排除关键词 */}
        <div>
          <label className="text-[11px] text-slate-500 mb-1.5 block">排除关键词（多个用空格分隔，任一匹配即排除）</label>
          <input value={config.exclude} onChange={e => set("exclude", e.target.value)}
            placeholder="如：CAM TS"
            className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-blue-500/50 placeholder:text-slate-600" />
        </div>

        {/* 自定义搜索词 */}
        <div>
          <label className="text-[11px] text-slate-500 mb-1.5 block">自定义搜索词（留空使用默认别名搜索）</label>
          <input value={config.search_keyword} onChange={e => set("search_keyword", e.target.value)}
            placeholder="优先级最高，覆盖自动搜索词"
            className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-blue-500/50 placeholder:text-slate-600" />
        </div>

        {/* 订阅搜索源 */}
        <SubscribeSourceSelect
          selectedSources={config.sources}
          onChange={(sources) => setConfig(prev => ({ ...prev, sources }))}
        />

        {/* 保存路径 */}
        <div>
          <label className="text-[11px] text-slate-500 mb-1.5 block">保存路径（留空使用默认）</label>
          <input value={config.save_path} onChange={e => set("save_path", e.target.value)}
            placeholder="下载文件保存位置"
            className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white font-mono outline-none focus:border-blue-500/50 placeholder:text-slate-600" />
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-3 pt-2">
          <button onClick={onClose}
            className="flex-1 py-2.5 rounded-xl text-[12px] bg-white/[0.04] text-slate-400 hover:text-white hover:bg-white/[0.08] transition-colors">
            取消
          </button>
          <button onClick={() => onConfirm(config)}
            className="flex-1 py-2.5 rounded-xl text-[12px] font-bold bg-amber-600 hover:bg-amber-500 text-white transition-colors">
            确认订阅
          </button>
        </div>
      </div>
    </div>
  );
}
