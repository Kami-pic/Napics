// License Key 授权管理区域 — 设置页中的 Pro 授权模块
"use client";
import React, { useState, useEffect, useCallback } from "react";
import { fetchLicenseStatus, validateLicenseKey, clearLicense, type LicenseStatus } from "@/lib/api/license";

export default function LicenseSection() {
  const [status, setStatus] = useState<LicenseStatus | null>(null);
  const [inputKey, setInputKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const s = await fetchLicenseStatus();
      setStatus(s);
    } catch {
      // 后端不可用时忽略
    }
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  const handleValidate = async () => {
    if (!inputKey.trim()) {
      setMessage({ text: "请输入 License Key", ok: false });
      return;
    }
    setLoading(true);
    setMessage(null);
    try {
      const result = await validateLicenseKey(inputKey.trim());
      if (result.success) {
        setMessage({ text: `✓ ${result.message}（${result.plan === "lifetime" ? "终身授权" : result.plan}）`, ok: true });
        setInputKey("");
        await loadStatus();
      } else {
        setMessage({ text: result.message || result.error || "验证失败", ok: false });
      }
    } catch (e: any) {
      setMessage({ text: e?.message || "验证失败", ok: false });
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    setLoading(true);
    try {
      await clearLicense();
      setMessage({ text: "已清除授权", ok: true });
      await loadStatus();
    } catch {
      setMessage({ text: "清除失败", ok: false });
    } finally {
      setLoading(false);
    }
  };

  const isPro = status?.is_pro;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-medium text-slate-300">Pro 授权</h3>
        {isPro && (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/15 text-emerald-400">
            已激活
          </span>
        )}
      </div>

      {isPro ? (
        <div className="p-3 bg-emerald-500/5 border border-emerald-500/10 rounded-lg space-y-2">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-300">
                {status?.plan === "lifetime" ? "🎫 终身授权" : `📅 ${status?.plan || "授权"}`}
              </p>
              {status?.email && <p className="text-[10px] text-slate-500 mt-0.5">{status.email}</p>}
            </div>
            <button onClick={handleClear} disabled={loading}
              className="text-[10px] text-red-400/60 hover:text-red-400 disabled:opacity-50">
              解除绑定
            </button>
          </div>
          {status?.validated_at && (
            <p className="text-[10px] text-slate-600">
              验证时间：{new Date(status.validated_at).toLocaleDateString()}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-[11px] text-slate-500">
            输入 License Key 解锁 Pro 插件（AI 智能整理、全链路自动化等）
          </p>
          <div className="flex gap-2">
            <input
              value={inputKey}
              onChange={e => setInputKey(e.target.value)}
              placeholder="粘贴 License Key..."
              className="flex-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50 font-mono"
              onKeyDown={e => { if (e.key === "Enter" && !loading) handleValidate(); }}
            />
            <button onClick={handleValidate} disabled={loading || !inputKey.trim()}
              className="px-4 py-2 rounded-lg text-xs bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 disabled:opacity-50 flex-shrink-0">
              {loading ? "验证中..." : "验证"}
            </button>
          </div>
        </div>
      )}

      {message && (
        <p className={`text-[11px] ${message.ok ? "text-emerald-400" : "text-red-400"}`}>
          {message.text}
        </p>
      )}
    </div>
  );
}
