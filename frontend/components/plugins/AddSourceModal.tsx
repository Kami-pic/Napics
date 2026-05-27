// 添加外部插件源弹窗
"use client";
import React, { useState } from "react";
import { addPluginSource } from "@/lib/api/plugins";

interface AddSourceModalProps {
  onClose: () => void;
  onAdded: () => void;
}

export default function AddSourceModal({ onClose, onAdded }: AddSourceModalProps) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!url.trim()) {
      setError("请输入插件源地址");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await addPluginSource(name.trim(), url.trim());
      onAdded();
    } catch (e: any) {
      const msg = e?.message || e?.error || "添加失败";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-[#1a1a1a] border border-white/[0.08] rounded-2xl w-full max-w-md p-6 shadow-2xl">
        <h3 className="text-sm font-semibold text-slate-200 mb-4">添加插件源</h3>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-slate-500 mb-1 block">名称（可选）</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="如：社区插件源"
              className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">地址</label>
            <input
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://github.com/user/napics-plugins"
              className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50"
            />
            <p className="text-[10px] text-slate-600 mt-1">
              支持 GitHub 仓库地址或直接指向 index.json 的 URL
            </p>
          </div>
        </div>

        {error && (
          <div className="mt-3 px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs text-slate-400 hover:text-slate-200 hover:bg-white/5">
            取消
          </button>
          <button onClick={handleSubmit} disabled={loading}
            className="px-4 py-2 rounded-lg text-xs bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 disabled:opacity-50">
            {loading ? "验证中..." : "添加"}
          </button>
        </div>

        {/* 安全提示 */}
        <div className="mt-4 px-3 py-2 bg-amber-500/5 border border-amber-500/10 rounded-lg">
          <p className="text-[10px] text-amber-400/80">
            ⚠️ 第三方插件源可能包含未经审核的代码，请只添加你信任的来源。
          </p>
        </div>
      </div>
    </div>
  );
}
