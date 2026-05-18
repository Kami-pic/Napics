// 插件配置弹窗
"use client";
import React, { useState, useEffect } from "react";
import { fetchPluginConfig, updatePluginConfig, type PluginInfo } from "@/lib/api/plugins";

interface PluginConfigModalProps {
  plugin: PluginInfo;
  onClose: () => void;
  onSaved: () => void;
}

const CONFIG_LABELS: Record<string, string> = {
  tmdb_api_key: "TMDB API Key",
  prowlarr_url: "Prowlarr 地址",
  prowlarr_api_key: "Prowlarr API Key",
  qb_url: "qBittorrent 地址",
  qb_username: "qB 用户名",
  qb_password: "qB 密码",
  alist_url: "OpenList/Alist 地址",
  alist_token: "Alist Token",
};

export default function PluginConfigModal({ plugin, onClose, onSaved }: PluginConfigModalProps) {
  const [config, setConfig] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchPluginConfig(plugin.id)
      .then(data => setConfig(data.config))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [plugin.id]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updatePluginConfig(plugin.id, config);
      onSaved();
    } catch (e) {
      console.error("保存配置失败", e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-[#1a1a1a] border border-white/[0.08] rounded-2xl w-full max-w-md p-6 shadow-2xl">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xl">{plugin.icon}</span>
          <h3 className="text-sm font-semibold text-slate-200">{plugin.name} 配置</h3>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-5 h-5 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin" />
          </div>
        ) : (
          <div className="space-y-3">
            {Object.entries(config).map(([key, value]) => (
              <div key={key}>
                <label className="text-xs text-slate-500 mb-1 block">
                  {CONFIG_LABELS[key] || key}
                </label>
                <input
                  type={key.includes("password") || key.includes("key") || key.includes("token") ? "password" : "text"}
                  value={value}
                  onChange={e => setConfig(prev => ({ ...prev, [key]: e.target.value }))}
                  className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-blue-500/40 placeholder:text-slate-600"
                  placeholder={`输入 ${CONFIG_LABELS[key] || key}`}
                />
              </div>
            ))}
          </div>
        )}

        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs text-slate-400 hover:text-slate-200 hover:bg-white/5">
            取消
          </button>
          <button onClick={handleSave} disabled={saving || loading}
            className="px-4 py-2 rounded-lg text-xs text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-50 transition-all">
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
