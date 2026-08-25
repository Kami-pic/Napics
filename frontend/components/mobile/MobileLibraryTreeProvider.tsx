// 应用级 /library/tree 只读缓存。
//
// 为什么必须是应用级：这个接口返回整棵目录树和所有视频对象，构树要全树递归，
// 而经 /backend 代理时 gzip 不生效（代理无条件 accept-encoding: identity 保 SSE 实时性）。
// 手机切 Tab 会重挂载页面组件，每次重拉一遍在 NAS 链路上是纯浪费。
//
// 页面只读不写。归位入库确认和「快速同步」成功后由调用方显式 invalidate()。
"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import type { FolderNode } from "@/types";
import { api } from "@/lib/api";

export interface MobileLibraryTreeState {
  tree: FolderNode | null;
  ready: boolean;
  loading: boolean;
  loadFailed: boolean;
  /** 每成功加载一次 +1。等待入库确认时用它判断"树已经刷过了" */
  version: number;
  /** 重新拉取；并发调用只会产生一个请求 */
  reload: () => Promise<void>;
  /** 判断某个视频路径是否已在库里（归位后确认入库用）。O(1) */
  hasVideoPath: (filePath: string) => boolean;
  /**
   * 该目录下是否已有视频入库。
   * 归位确认只能用这个：归位搬过去的文件名来自沙盒，前端并不知道最终文件名，
   * 只知道 save_path。
   */
  hasVideoUnder: (dirPath: string) => boolean;
}

/** 统一分隔符再比前缀：save_path 和 file_path 同源，但可能混用 \ 与 / */
function normalizeDir(dirPath: string): string {
  return dirPath.replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
}

const MobileLibraryTreeContext = createContext<MobileLibraryTreeState | null>(null);

export function useMobileLibraryTree(): MobileLibraryTreeState {
  const ctx = useContext(MobileLibraryTreeContext);
  if (!ctx) throw new Error("useMobileLibraryTree 必须在 MobileProviders 内使用");
  return ctx;
}

/** 全树递归收集视频路径。只在每次加载后做一次，之后查找都是 O(1) */
function collectVideoPaths(node: FolderNode | null): Set<string> {
  const paths = new Set<string>();
  if (!node) return paths;
  const stack: FolderNode[] = [node];
  while (stack.length) {
    const current = stack.pop()!;
    for (const video of current.videos || []) {
      if (video.file_path) paths.add(video.file_path);
    }
    for (const child of current.children || []) stack.push(child);
  }
  return paths;
}

export default function MobileLibraryTreeProvider({ children }: { children: ReactNode }) {
  const [tree, setTree] = useState<FolderNode | null>(null);
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [version, setVersion] = useState(0);

  // 在途请求：重复调用 reload 时复用同一个 promise，不叠加请求
  const inFlightRef = useRef<Promise<void> | null>(null);
  // Strict Mode 下 effect 跑两次，没有闸门就会打两次整树请求
  const startedRef = useRef(false);
  const pathsRef = useRef<Set<string>>(new Set());

  const reload = useCallback(async () => {
    if (inFlightRef.current) return inFlightRef.current;

    const task = (async () => {
      setLoading(true);
      try {
        const next = await api.getLibraryTree();
        setTree(next);
        pathsRef.current = collectVideoPaths(next);
        setLoadFailed(false);
        setVersion(v => v + 1);
      } catch {
        setLoadFailed(true);
      } finally {
        setLoading(false);
        setReady(true);
        inFlightRef.current = null;
      }
    })();

    inFlightRef.current = task;
    return task;
  }, []);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    void reload();
  }, [reload]);

  const hasVideoPath = useCallback((filePath: string) => {
    if (!filePath) return false;
    return pathsRef.current.has(filePath);
  }, []);

  const hasVideoUnder = useCallback((dirPath: string) => {
    const prefix = normalizeDir(dirPath);
    if (!prefix) return false;
    for (const path of pathsRef.current) {
      const normalized = path.replace(/\\/g, "/").toLowerCase();
      if (normalized.startsWith(prefix + "/")) return true;
    }
    return false;
  }, []);

  const value = useMemo<MobileLibraryTreeState>(() => ({
    tree, ready, loading, loadFailed, version, reload, hasVideoPath, hasVideoUnder,
  }), [tree, ready, loading, loadFailed, version, reload, hasVideoPath, hasVideoUnder]);

  return (
    <MobileLibraryTreeContext.Provider value={value}>
      {children}
    </MobileLibraryTreeContext.Provider>
  );
}
