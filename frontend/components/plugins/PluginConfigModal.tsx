// 插件 manifest schema 驱动的配置弹窗
"use client";

import { useEffect, useState } from "react";
import {
  fetchPluginConfig,
  updatePluginConfig,
  type PluginConfigField,
  type PluginInfo,
} from "@/lib/api/plugins";

export interface PluginConfigModalProps {
  plugin: PluginInfo;
  onClose: () => void;
  onSaved: () => void;
}

export default function PluginConfigModal({ plugin, onClose, onSaved }: PluginConfigModalProps) {
  const [config, setConfig] = useState<Record<string, string>>({});
  const [schema, setSchema] = useState<PluginConfigField[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    fetchPluginConfig(plugin.id)
      .then(data => {
        setConfig(data.config);
        setSchema(data.schema);
      })
      .catch(err => setError(err instanceof Error ? err.message : "获取插件配置失败"))
      .finally(() => setLoading(false));
  }, [plugin.id]);

  const handleSave = async () => {
    const missing = schema.find(field => field.required && !config[field.key]?.trim());
    if (missing) {
      setError(`请填写 ${missing.label || missing.key}`);
      return;
    }

    setSaving(true);
    setError("");
    try {
      await updatePluginConfig(plugin.id, config);
      window.dispatchEvent(new Event("plugins-changed"));
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存插件配置失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full max-w-md rounded-2xl border border-white/[0.08] bg-[var(--background)] p-6 shadow-2xl">
        <div className="mb-4 flex items-center gap-2">
          <span className="text-xl">{plugin.icon}</span>
          <h3 className="text-sm font-semibold text-slate-200">{plugin.name} 配置</h3>
        </div>

        {error && (
          <div className="mb-3 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-700 border-t-blue-500" />
          </div>
        ) : (
          <div className="space-y-3">
            {schema.map(field => (
              <div key={field.key}>
                <label className="mb-1 block text-xs text-slate-400">
                  {field.label || field.key}{field.required ? " *" : ""}
                </label>
                {field.description && (
                  <p className="mb-1.5 text-[10px] text-slate-600">{field.description}</p>
                )}
                <input
                  type={field.type || "text"}
                  value={config[field.key] || ""}
                  onChange={event => setConfig(previous => ({
                    ...previous,
                    [field.key]: event.target.value,
                  }))}
                  className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-sm text-slate-300 outline-none placeholder:text-slate-600 focus:border-blue-500/40"
                  placeholder={field.placeholder || `输入 ${field.label || field.key}`}
                />
              </div>
            ))}
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose}
            className="rounded-lg px-4 py-2 text-xs text-slate-400 hover:bg-white/5 hover:text-slate-200">
            取消
          </button>
          <button onClick={handleSave} disabled={saving || loading}
            className="rounded-lg bg-blue-600 px-4 py-2 text-xs text-white transition-all hover:bg-blue-500 disabled:opacity-50">
            {saving ? "保存中..." : "保存并应用"}
          </button>
        </div>
      </div>
    </div>
  );
}
