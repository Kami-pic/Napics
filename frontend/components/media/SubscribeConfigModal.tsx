// 订阅配置弹窗：点击订阅按钮后弹出，配置订阅类型、质量、搜索源等
"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import SubscribeSourceSelect from "./SubscribeSourceSelect";

export interface SubscribeConfig {
  quality: string;
  target_quality: string;
  include: string;
  exclude: string;
  mode: "notify" | "auto";
  best_version: boolean;
  save_path: string;
  search_keyword: string;
  sources: string[];
  purpose: "follow" | "upgrade";
}

export interface SubscribeConfigModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (config: SubscribeConfig) => void;
  title: string;
  mediaType: string;
  defaultSavePath?: string;
  /** 洗版模式预填：当前质量分 */
  currentQualityScore?: number;
  /** 洗版模式预填：当前质量标签 */
  currentQualityTag?: string;
}

const QUALITY_OPTIONS = [
  { value: "2160p", label: "4K" },
  { value: "1080p", label: "1080p" },
  { value: "720p", label: "720p" },
  { value: "", label: "不限" },
];

const TARGET_QUALITY_OPTIONS = [
  { value: "2160p", label: "4K" },
  { value: "1080p", label: "1080p" },
  { value: "", label: "不设" },
];

export default function SubscribeConfigModal({
  open, onClose, onConfirm, title, mediaType, defaultSavePath = "",
  currentQualityScore, currentQualityTag,
}: SubscribeConfigModalProps) {
  const [config, setConfig] = useState<SubscribeConfig>({
    quality: "1080p",
    target_quality: "",
    include: "",
    exclude: "",
    mode: "notify",
    best_version: false,
    save_path: defaultSavePath,
    search_keyword: "",
    sources: [],
    purpose: "follow",
  });
  const [showAdvanced, setShowAdvanced] = useState(false);

  // 加载分类保存路径
  const [savePaths, setSavePaths] = useState<Record<string, string[]>>({});
  useEffect(() => {
    if (!open) return;
    api.getSubscriptionSavePaths()
      .then(data => {
        setSavePaths(data.paths || {});
        // 根据 mediaType 自动填入保存路径（如果用户没手动设置）
        if (!config.save_path && !defaultSavePath) {
          const tag = mediaType === "tv" ? "tv" : "movie";
          const paths = data.paths?.[tag];
          if (paths && paths.length > 0) {
            setConfig(prev => ({ ...prev, save_path: paths[0] }));
          }
        }
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, mediaType]);

  if (!open) return null;

  const set = <K extends keyof SubscribeConfig>(key: K, value: SubscribeConfig[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const isUpgrade = config.purpose === "upgrade";

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[60]">
      <div className="bg-[#1a1a1a] border border-white/[0.08] rounded-2xl w-full max-w-md p-6 space-y-4 max-h-[85vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h3 className="text-[15px] font-bold text-white">订阅设置</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white text-lg">✕</button>
        </div>
        <p className="text-[12px] text-slate-400 -mt-2">
          {title} · <span className={mediaType === "tv" ? "text-blue-400" : "text-amber-400"}>{mediaType === "tv" ? "📺 剧集" : "🎬 电影"}</span>
        </p>

        {/* 订阅类型 */}
        <div>
          <label className="text-[11px] text-slate-500 mb-1.5 block">订阅类型</label>
          <div className="flex gap-2">
            <button onClick={() => { set("purpose", "follow"); set("best_version", false); }}
              className={`flex-1 py-2 rounded-lg text-[12px] transition-colors ${
                !isUpgrade ? "bg-blue-600 text-white" : "bg-white/[0.04] text-slate-400 hover:text-white"
              }`}>🔄 追更</button>
            <button onClick={() => { set("purpose", "upgrade"); set("best_version", true); set("mode", "auto"); }}
              className={`flex-1 py-2 rounded-lg text-[12px] transition-colors ${
                isUpgrade ? "bg-emerald-600 text-white" : "bg-white/[0.04] text-slate-400 hover:text-white"
              }`}>⬆️ 洗版</button>
          </div>
        </div>

        {/* 洗版模式：当前质量信息 */}
        {isUpgrade && currentQualityTag && (
          <div className="px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
            <span className="text-[11px] text-slate-500">当前质量：</span>
            <span className="text-[12px] text-slate-300 ml-1">{currentQualityTag}</span>
            {currentQualityScore !== undefined && (
              <span className="text-[11px] text-slate-600 ml-2">({currentQualityScore}分)</span>
            )}
          </div>
        )}

        {/* 质量偏好 */}
        <div>
          <label className="text-[11px] text-slate-500 mb-1.5 block">
            {isUpgrade ? "最低接受质量" : "最低质量要求"}
            <span className="text-slate-600 ml-1">（低于此质量的资源会被过滤）</span>
          </label>
          <div className="flex gap-2">
            {QUALITY_OPTIONS.map(q => (
              <button key={q.value} onClick={() => set("quality", q.value)}
                className={`px-3 py-1.5 rounded-lg text-[11px] transition-colors ${
                  config.quality === q.value ? "bg-blue-600 text-white" : "bg-white/[0.04] text-slate-400 hover:text-white"
                }`}>{q.label}</button>
            ))}
          </div>
        </div>

        {/* 目标质量（Quality Cutoff） */}
        <div>
          <label className="text-[11px] text-slate-500 mb-1.5 block">
            目标质量
            <span className="text-slate-600 ml-1">（达到后停止搜索更好版本）</span>
          </label>
          <div className="flex gap-2">
            {TARGET_QUALITY_OPTIONS.map(q => (
              <button key={q.value} onClick={() => set("target_quality", q.value)}
                className={`px-3 py-1.5 rounded-lg text-[11px] transition-colors ${
                  config.target_quality === q.value ? "bg-blue-600 text-white" : "bg-white/[0.04] text-slate-400 hover:text-white"
                }`}>{q.label}</button>
            ))}
          </div>
        </div>

        {/* 下载模式（追更模式才显示选择，洗版固定自动） */}
        {!isUpgrade && (
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
        )}

        {/* 订阅搜索源 */}
        <SubscribeSourceSelect
          selectedSources={config.sources}
          onChange={(sources) => set("sources", sources)}
          mediaType={mediaType}
        />

        {/* 高级设置折叠 */}
        <button onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-[11px] text-slate-500 hover:text-slate-300 transition-colors flex items-center gap-1">
          <span className={`transition-transform ${showAdvanced ? "rotate-90" : ""}`}>▸</span>
          高级设置
        </button>

        {showAdvanced && (
          <div className="space-y-3 pl-2 border-l border-white/[0.06]">
            {/* 自动洗版（追更模式下可选） */}
            {!isUpgrade && (
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
            )}
            {/* 包含关键词 */}
            <div>
              <label className="text-[11px] text-slate-500 mb-1 block">包含关键词</label>
              <input value={config.include} onChange={e => set("include", e.target.value)}
                placeholder="如：HEVC 中字（空格分隔，全部匹配）"
                className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-blue-500/50 placeholder:text-slate-600" />
            </div>
            {/* 排除关键词 */}
            <div>
              <label className="text-[11px] text-slate-500 mb-1 block">排除关键词</label>
              <input value={config.exclude} onChange={e => set("exclude", e.target.value)}
                placeholder="如：CAM TS（空格分隔，任一排除）"
                className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-blue-500/50 placeholder:text-slate-600" />
            </div>
            {/* 自定义搜索词 */}
            <div>
              <label className="text-[11px] text-slate-500 mb-1 block">自定义搜索词</label>
              <input value={config.search_keyword} onChange={e => set("search_keyword", e.target.value)}
                placeholder="留空使用默认别名搜索"
                className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-blue-500/50 placeholder:text-slate-600" />
            </div>
            {/* 保存路径 */}
            <div>
              <label className="text-[11px] text-slate-500 mb-1 block">保存路径</label>
              <input value={config.save_path} onChange={e => set("save_path", e.target.value)}
                placeholder={defaultSavePath || savePaths[mediaType === "tv" ? "tv" : "movie"]?.[0] || "留空使用默认"}
                className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white font-mono outline-none focus:border-blue-500/50 placeholder:text-slate-600" />
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex gap-3 pt-2">
          <button onClick={onClose}
            className="flex-1 py-2.5 rounded-xl text-[12px] bg-white/[0.04] text-slate-400 hover:text-white hover:bg-white/[0.08] transition-colors">
            取消
          </button>
          <button onClick={() => onConfirm(config)}
            className={`flex-1 py-2.5 rounded-xl text-[12px] font-bold text-white transition-colors ${
              isUpgrade ? "bg-emerald-600 hover:bg-emerald-500" : "bg-amber-600 hover:bg-amber-500"
            }`}>
            {isUpgrade ? "开始蹲守" : "确认订阅"}
          </button>
        </div>
      </div>
    </div>
  );
}
