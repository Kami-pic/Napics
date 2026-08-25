// 移动端应用级只读状态：插件可用性 + 配置。
//
// 只在 app/m/layout.tsx 里包裹。**不动根 app/layout.tsx** —— 它是 Server Component，
// 改它会波及桌面 / 与 /manage。
//
// 存在的理由是"每个页面各自请求一次"太贵：插件列表和配置在一次浏览会话里不会变，
// 而移动端切 Tab 就会重挂载页面组件。
"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type { AppConfig } from "@/types";
import { api } from "@/lib/api";
import { useInstalledPlugins, type InstalledPluginsState } from "@/hooks/useInstalledPlugins";
import MobileLibraryTreeProvider from "./MobileLibraryTreeProvider";

// ── 插件 ──

const MobilePluginContext = createContext<InstalledPluginsState | null>(null);

export function useMobilePlugins(): InstalledPluginsState {
  const ctx = useContext(MobilePluginContext);
  if (!ctx) throw new Error("useMobilePlugins 必须在 MobileProviders 内使用");
  return ctx;
}

// ── 配置 ──

export interface MobileConfigState {
  config: AppConfig | null;
  ready: boolean;
  loadFailed: boolean;
  /** 下载保存路径的默认值：第一个扫描路径 */
  defaultSavePath: string;
  reload: () => void;
}

const MobileConfigContext = createContext<MobileConfigState | null>(null);

export function useMobileConfig(): MobileConfigState {
  const ctx = useContext(MobileConfigContext);
  if (!ctx) throw new Error("useMobileConfig 必须在 MobileProviders 内使用");
  return ctx;
}

function MobileConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [ready, setReady] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  // Strict Mode 下 effect 会跑两次，没有这个闸门就会打两次 /config
  const loadedRef = useRef(false);

  const load = useCallback(async () => {
    try {
      setConfig(await api.getConfig());
      setLoadFailed(false);
    } catch {
      setLoadFailed(true);
    } finally {
      setReady(true);
    }
  }, []);

  const reload = useCallback(() => {
    loadedRef.current = true;
    void load();
  }, [load]);

  useEffect(() => {
    if (loadedRef.current) return;
    loadedRef.current = true;
    void load();
  }, [load]);

  const value = useMemo<MobileConfigState>(() => ({
    config,
    ready,
    loadFailed,
    defaultSavePath: config?.scan_paths?.[0] || "",
    reload,
  }), [config, ready, loadFailed, reload]);

  return <MobileConfigContext.Provider value={value}>{children}</MobileConfigContext.Provider>;
}

function MobilePluginProvider({ children }: { children: ReactNode }) {
  const plugins = useInstalledPlugins();
  return <MobilePluginContext.Provider value={plugins}>{children}</MobilePluginContext.Provider>;
}

export default function MobileProviders({ children }: { children: ReactNode }) {
  return (
    <MobilePluginProvider>
      <MobileConfigProvider>
        <MobileLibraryTreeProvider>{children}</MobileLibraryTreeProvider>
      </MobileConfigProvider>
    </MobilePluginProvider>
  );
}
