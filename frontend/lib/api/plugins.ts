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
  source?: string;  // builtin / remote
}

export interface PluginConfig {
  plugin_id: string;
  config: Record<string, string>;
}

export interface PluginSource {
  name: string;
  url: string;
}

export interface RemotePluginItem {
  id: string;
  name: string;
  version: string;
  description: string;
  category: string;
  icon: string;
  risk_level: string;
  depends_on: string[];
  download_url: string;
  installed: boolean;
  source: string;
  source_name: string;
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

// ── 外部插件源 API ──

export async function fetchPluginSources(): Promise<PluginSource[]> {
  const res = await fetch(`${BASE_URL}/api/plugins/sources`);
  if (!res.ok) throw new Error("获取插件源列表失败");
  const data = await res.json();
  return data.sources;
}

export async function addPluginSource(name: string, url: string): Promise<{ success: boolean; source: PluginSource }> {
  const res = await fetch(`${BASE_URL}/api/plugins/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, url }),
  });
  if (!res.ok) {
    const detail = await res.json();
    throw detail.detail || detail;
  }
  return res.json();
}

export async function removePluginSource(url: string): Promise<{ success: boolean }> {
  const res = await fetch(`${BASE_URL}/api/plugins/sources`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const detail = await res.json();
    throw detail.detail || detail;
  }
  return res.json();
}

export async function fetchRemotePlugins(sourceUrl?: string): Promise<{ plugins: RemotePluginItem[]; errors: Array<{ url: string; error: string }> }> {
  const params = sourceUrl ? `?source_url=${encodeURIComponent(sourceUrl)}` : "";
  const res = await fetch(`${BASE_URL}/api/plugins/sources/plugins${params}`);
  if (!res.ok) throw new Error("获取远程插件列表失败");
  return res.json();
}

export async function installRemotePlugin(sourceUrl: string, pluginId: string): Promise<{ success: boolean; installed_plugins: string[] }> {
  const res = await fetch(`${BASE_URL}/api/plugins/install-remote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_url: sourceUrl, plugin_id: pluginId }),
  });
  if (!res.ok) {
    const detail = await res.json();
    throw detail.detail || detail;
  }
  return res.json();
}
