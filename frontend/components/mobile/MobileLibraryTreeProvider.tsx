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
  /**
   * 确保树已经加载过一次（幂等）。
   * **需要树的页面必须自己调它** —— Provider 挂在 app/m/layout.tsx 上，
   * 如果在这里自动加载，`/m/search` 和 `/m/play` 也会白拉一棵整树。
   */
  ensureLoaded: () => void;
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

interface VideoIndex {
  /** 原样的 file_path，用于精确匹配 */
  paths: Set<string>;
  /** 每个视频的全部祖先目录（已归一化），用于"这个目录下有没有视频"的判断。
   *  预先展开是为了让查询是一次 Set.has 而不是遍历全库做前缀匹配 ——
   *  下载页轮询期间每个已归位任务每轮会查好几次，2600 条库下遍历太浪费。 */
  dirs: Set<string>;
}

/** 全树递归建索引。只在每次加载后做一次，之后查找都是 O(1) */
function buildVideoIndex(node: FolderNode | null): VideoIndex {
  const paths = new Set<string>();
  const dirs = new Set<string>();
  if (!node) return { paths, dirs };

  const stack: FolderNode[] = [node];
  while (stack.length) {
    const current = stack.pop()!;
    for (const video of current.videos || []) {
      const filePath = video.file_path;
      if (!filePath) continue;
      paths.add(filePath);
      // 把该视频的每一级父目录都记下来
      let dir = normalizeDir(filePath.slice(0, Math.max(
        filePath.lastIndexOf("\\"), filePath.lastIndexOf("/"),
      )));
      while (dir && !dirs.has(dir)) {
        dirs.add(dir);
        const cut = dir.lastIndexOf("/");
        if (cut <= 0) break;
        dir = dir.slice(0, cut);
      }
    }
    for (const child of current.children || []) stack.push(child);
  }
  return { paths, dirs };
}

export default function MobileLibraryTreeProvider({ children }: { children: ReactNode }) {
  const [tree, setTree] = useState<FolderNode | null>(null);
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [version, setVersion] = useState(0);

  // 在途请求：重复调用 reload 时复用同一个 promise，不叠加请求
  const inFlightRef = useRef<Promise<void> | null>(null);
  // 是否已经加载过。同时兼作 Strict Mode 的闸门（effect 跑两次不会打两次请求）
  const startedRef = useRef(false);
  const indexRef = useRef<VideoIndex>({ paths: new Set(), dirs: new Set() });

  const reload = useCallback(async () => {
    if (inFlightRef.current) return inFlightRef.current;

    const task = (async () => {
      setLoading(true);
      try {
        const next = await api.getLibraryTree();
        setTree(next);
        indexRef.current = buildVideoIndex(next);
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

  const ensureLoaded = useCallback(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    void reload();
  }, [reload]);

  const hasVideoPath = useCallback((filePath: string) => {
    if (!filePath) return false;
    return indexRef.current.paths.has(filePath);
  }, []);

  const hasVideoUnder = useCallback((dirPath: string) => {
    const key = normalizeDir(dirPath);
    if (!key) return false;
    return indexRef.current.dirs.has(key);
  }, []);

  const value = useMemo<MobileLibraryTreeState>(() => ({
    tree, ready, loading, loadFailed, version,
    reload, ensureLoaded, hasVideoPath, hasVideoUnder,
  }), [tree, ready, loading, loadFailed, version, reload, ensureLoaded, hasVideoPath, hasVideoUnder]);

  return (
    <MobileLibraryTreeContext.Provider value={value}>
      {children}
    </MobileLibraryTreeContext.Provider>
  );
}
