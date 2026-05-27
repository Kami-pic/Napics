// 从 GitHub URL 直接安装插件
"use client";
import React, { useState } from "react";
import { installFromUrl } from "@/lib/api/plugins";

interface InstallFromUrlProps {
  onInstalled: () => void;
}

export default function InstallFromUrl({ onInstalled }: InstallFromUrlProps) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleInstall = async () => {
    if (!url.trim()) {
      setError("请输入 GitHub 仓库地址");
      return;
    }
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const result = await installFromUrl(url.trim());
      setSuccess(`插件 "${result.name || result.plugin_id}" 安装成功`);
      setUrl("");
      onInstalled();
    } catch (e: any) {
      const msg = e?.message || e?.error || "安装失败";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs text-slate-400 mb-3">
          输入 GitHub 仓库地址，直接安装插件。仓库根目录需包含 <code className="text-blue-400/80 bg-blue-500/10 px-1 rounded">manifest.json</code>。
        </p>
        <input
          value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="https://github.com/用户名/插件仓库"
          className="w-full px-3 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50"
          onKeyDown={e => { if (e.key === "Enter" && !loading) handleInstall(); }}
        />
      </div>

      <button
        onClick={handleInstall}
        disabled={loading || !url.trim()}
        className="w-full px-4 py-2.5 rounded-lg text-xs bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 disabled:opacity-50 transition-all"
      >
        {loading ? "安装中..." : "安装插件"}
      </button>

      {error && (
        <div className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
          {error}
          <button onClick={() => setError("")} className="ml-2 text-red-500 hover:text-red-300">✕</button>
        </div>
      )}

      {success && (
        <div className="px-3 py-2 bg-green-500/10 border border-green-500/20 rounded-lg text-xs text-green-400">
          {success}
        </div>
      )}

      {/* 使用说明 */}
      <div className="mt-6 space-y-3">
        <h4 className="text-xs text-slate-500 font-medium">支持的格式</h4>
        <div className="space-y-2 text-[11px] text-slate-600">
          <p>• <code className="text-slate-400">https://github.com/user/my-plugin</code></p>
          <p>• <code className="text-slate-400">https://github.com/user/my-plugin/tree/dev</code>（指定分支）</p>
        </div>

        <h4 className="text-xs text-slate-500 font-medium mt-4">仓库要求</h4>
        <div className="space-y-1 text-[11px] text-slate-600">
          <p>• 根目录包含 <code className="text-slate-400">manifest.json</code>（声明插件 ID、名称、类型）</p>
          <p>• 根目录包含 <code className="text-slate-400">__init__.py</code>（注册入口，导出 register 函数）</p>
        </div>
      </div>

      {/* 安全提示 */}
      <div className="px-3 py-2 bg-amber-500/5 border border-amber-500/10 rounded-lg">
        <p className="text-[10px] text-amber-400/80">
          ⚠️ 从 URL 安装的插件未经审核，请只安装你信任的来源。
        </p>
      </div>
    </div>
  );
}
