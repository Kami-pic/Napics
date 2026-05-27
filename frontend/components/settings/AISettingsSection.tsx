// AI 助手设置区域（从 SettingsModal 拆分）
"use client";
import { useState, useEffect } from "react";
import type { AppConfig, AIFeaturesConfig } from "@/types";

// AI 服务商预设
const AI_PRESETS: { label: string; base_url: string; hint: string }[] = [
  { label: "豆包", base_url: "https://ark.cn-beijing.volces.com/api/v3", hint: "模型字段填推理接入点 ID（ep-xxx 格式），需先在火山引擎控制台创建" },
  { label: "DeepSeek", base_url: "https://api.deepseek.com", hint: "模型字段填 deepseek-chat 或 deepseek-reasoner" },
  { label: "自定义", base_url: "", hint: "手动填写 Base URL" },
];

// AI 场景描述
const AI_FEATURE_LIST: { key: keyof AIFeaturesConfig; label: string; desc: string; phase: 1 | 2 }[] = [
  { key: "extract_episode", label: "文件名智能解析", desc: "整理时自动识别乱码文件名", phase: 1 },
  { key: "scrape_candidate", label: "识别候选匹配", desc: "批量识别时自动选择最佳候选", phase: 1 },
  { key: "library_diagnosis", label: "媒体库诊断", desc: "AI 分析媒体库健康状况", phase: 1 },
  { key: "search_recommend", label: "搜索结果推荐", desc: "标记最值得下载的资源", phase: 2 },
  { key: "natural_search", label: "自然语言搜索", desc: "用自然语言描述想找的片", phase: 2 },
  { key: "subscribe_recommend", label: "订阅推荐", desc: "根据观影偏好推荐新片", phase: 2 },
];

interface AISettingsSectionProps {
  config: AppConfig;
  setConfig: (c: AppConfig) => void;
}

export function AISettingsSection({ config, setConfig }: AISettingsSectionProps) {
  const [aiTestResult, setAiTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [aiTesting, setAiTesting] = useState(false);
  const [aiUsage, setAiUsage] = useState<Record<string, { calls: number; tokens: number }>>({});
  const [aiExpanded, setAiExpanded] = useState(false);

  useEffect(() => {
    fetch("http://localhost:8000/ai/status").then(r => r.json()).then(data => {
      setAiUsage(data.usage || {});
    }).catch(() => {});
    setAiTestResult(null);
  }, []);

  return (
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
              const { api } = await import("@/lib/api");
              await api.saveConfig(config);
              const r = await api.testAIConnection();
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
  );
}
