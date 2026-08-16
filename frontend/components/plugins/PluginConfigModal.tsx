// 插件 manifest schema 驱动的配置弹窗
"use client";

import { useEffect, useState } from "react";
import {
  fetchPluginConfig,
  updatePluginConfig,
  testPluginConnection,
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
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
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

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testPluginConnection(plugin.id);
      setTestResult({
        success: result.success,
        message: result.success
          ? `连接成功${result.version ? ` (${result.version})` : ""}${result.username ? ` 用户: ${result.username}` : ""}`
          : result.error || "连接失败",
      });
    } catch (err) {
      setTestResult({ success: false, message: err instanceof Error ? err.message : "测试失败" });
    } finally {
      setTesting(false);
    }
  };

  // 找到 url 类型的字段值作为直达链接
  const urlField = schema.find(f => f.type === "url");
  const directUrl = urlField ? config[urlField.key] : "";

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full max-w-md rounded-2xl border border-white/[0.08] bg-[var(--background)] p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">{plugin.icon}</span>
            <h3 className="text-sm font-semibold text-slate-200">{plugin.name} 配置</h3>
          </div>
          {directUrl && (
            <a href={directUrl} target="_blank" rel="noopener noreferrer"
              className="text-[11px] text-blue-400 hover:text-blue-300 hover:underline">
              打开管理面板 ↗
            </a>
          )}
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

        {/* 测试结果 */}
        {testResult && (
          <div className={`mt-3 rounded-lg border px-3 py-2 text-xs ${
            testResult.success
              ? "border-green-500/20 bg-green-500/10 text-green-400"
              : "border-red-500/20 bg-red-500/10 text-red-400"
          }`}>
            {testResult.success ? "✓ " : "✗ "}{testResult.message}
          </div>
        )}

        <div className="mt-5 flex items-center justify-between">
          <button onClick={handleTest} disabled={testing || loading}
            className="rounded-lg border border-white/[0.08] px-3 py-2 text-xs text-slate-400 hover:bg-white/5 hover:text-slate-200 disabled:opacity-50">
            {testing ? "测试中..." : "🔌 测试连接"}
          </button>
          <div className="flex gap-2">
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
    </div>
  );
}
