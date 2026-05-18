// 插件中心 API
import { BASE_URL } from "./base";

export interface PluginInfo {
  id: string;
  name: string;
  version: string;
  description: string;
  category: string;
  icon: string;
  requires_config: string[];
  depends_on: string[];
  provides: string[];
  risk_level: string;
  installed: boolean;
}

export interface PluginConfig {
  plugin_id: string;
  config: Record<string, string>;
}

export async function fetchPlugins(): Promise<PluginInfo[]> {
  const res = await fetch(`${BASE_URL}/api/plugins`);
  if (!res.ok) throw new Error("获取插件列表失败");
  return res.json();
}

export async function installPlugin(id: string): Promise<{ success: boolean; installed_plugins: string[] }> {
  const res = await fetch(`${BASE_URL}/api/plugins/install`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
  if (!res.ok) {
    const detail = await res.json();
    throw detail.detail || detail;
  }
  return res.json();
}

export async function uninstallPlugin(id: string): Promise<{ success: boolean; installed_plugins: string[] }> {
  const res = await fetch(`${BASE_URL}/api/plugins/uninstall`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
  if (!res.ok) {
    const detail = await res.json();
    throw detail.detail || detail;
  }
  return res.json();
}

export async function fetchPluginConfig(pluginId: string): Promise<PluginConfig> {
  const res = await fetch(`${BASE_URL}/api/plugins/${pluginId}/config`);
  if (!res.ok) throw new Error("获取插件配置失败");
  return res.json();
}

export async function updatePluginConfig(pluginId: string, config: Record<string, string>): Promise<{ success: boolean }> {
  const res = await fetch(`${BASE_URL}/api/plugins/${pluginId}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  });
  if (!res.ok) throw new Error("保存插件配置失败");
  return res.json();
}
