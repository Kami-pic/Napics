// 首次扫描完成后的可选配置引导
"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { AppConfig } from "@/types";

interface SetupWizardModalProps {
  open: boolean;
  config: AppConfig;
  onClose: () => void;
  onSaved: (config: AppConfig) => void;
}

export default function SetupWizardModal({ open, config, onClose, onSaved }: SetupWizardModalProps) {
  const [tmdbKey, setTmdbKey] = useState(config.tmdb_api_key || "");
  const [proxy, setProxy] = useState(config.http_proxy || "");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"" | "ok" | "fail">("");
  const [saving, setSaving] = useState(false);

  if (!open) return null;

  const handleTest = async () => {
    if (!tmdbKey.trim()) return;
    setTesting(true);
    setTestResult("");
    try {
      const testUrl = `https://api.themoviedb.org/3/configuration?api_key=${tmdbKey.trim()}`;
      const fetchOptions: RequestInit = {};
      // 注意：浏览器端无法直接使用代理，这里只测试 Key 有效性
      const resp = await fetch(testUrl, { signal: AbortSignal.timeout(8000) });
      setTestResult(resp.ok ? "ok" : "fail");
    } catch {
      setTestResult("fail");
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const newConfig = { ...config, tmdb_api_key: tmdbKey.trim(), http_proxy: proxy.trim() };
      await api.saveConfig(newConfig);
      onSaved(newConfig as AppConfig);
    } catch {
      // 静默失败，不阻塞用户
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const handleSkip = () => {
    // 标记已跳过，不再弹出
    localStorage.setItem("napics_setup_done", "1");
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-8 z-50"
      onClick={(e) => { if (e.target === e.currentTarget) handleSkip(); }}>
      <div className="bg-[var(--background)] border border-white/[0.06] rounded-2xl w-full max-w-md p-6">
        {/* 标题 */}
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center">
            <span className="text-lg">✨</span>
          </div>
          <div>
            <h2 className="text-base font-bold text-white">扫描完成</h2>
            <p className="text-xs text-slate-500">配置以下信息可解锁更多功能</p>
          </div>
        </div>

        {/* TMDB API Key */}
        <div className="mb-4">
          <label className="text-sm text-slate-300 mb-1.5 block font-medium">
            TMDB API Key
            <span className="text-slate-600 font-normal ml-1">推荐</span>
          </label>
          <p className="text-xs text-slate-500 mb-2">用于自动识别影视信息、获取封面和评分</p>
          <div className="flex gap-2">
            <input value={tmdbKey} onChange={e => { setTmdbKey(e.target.value); setTestResult(""); }}
              placeholder="输入你的 TMDB API Key"
              className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-blue-500/30 placeholder:text-slate-600" />
            <button onClick={handleTest} disabled={testing || !tmdbKey.trim()}
              className="px-3 py-2 rounded-lg text-xs bg-white/[0.06] hover:bg-white/[0.08] text-slate-400 disabled:opacity-40 transition-all">
              {testing ? "..." : "测试"}
            </button>
          </div>
          {testResult === "ok" && <p className="text-xs text-green-400 mt-1">✓ 连接成功</p>}
          {testResult === "fail" && <p className="text-xs text-red-400 mt-1">✗ 连接失败，请检查 Key 或网络/代理</p>}
          <a href="https://www.themoviedb.org/settings/api" target="_blank" rel="noopener"
            className="text-[10px] text-blue-400/70 hover:text-blue-400 mt-1 inline-block">
            如何获取 TMDB API Key →
          </a>
        </div>

        {/* 代理 */}
        <div className="mb-5">
          <label className="text-sm text-slate-300 mb-1.5 block font-medium">
            HTTP 代理
            <span className="text-slate-600 font-normal ml-1">可选</span>
          </label>
          <p className="text-xs text-slate-500 mb-2">访问 TMDB 等海外服务时使用</p>
          <input value={proxy} onChange={e => setProxy(e.target.value)}
            placeholder="如 http://127.0.0.1:7890"
            className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-blue-500/30 placeholder:text-slate-600" />
        </div>

        {/* 按钮 */}
        <div className="flex gap-3">
          <button onClick={handleSave} disabled={saving}
            className="flex-1 bg-blue-600 hover:bg-blue-500 py-2.5 rounded-xl text-sm font-medium transition-all disabled:opacity-50">
            {saving ? "保存中..." : "保存配置"}
          </button>
          <button onClick={handleSkip}
            className="flex-1 bg-white/[0.06] hover:bg-white/[0.08] py-2.5 rounded-xl text-sm text-slate-400 transition-all">
            稍后配置
          </button>
        </div>
      </div>
    </div>
  );
}
