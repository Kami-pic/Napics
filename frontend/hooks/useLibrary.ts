// 媒体库核心状态管理
"use client";
import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import type { VideoInfo, AppConfig, ScanProgress, FilterType, ViewMode, LibraryStats, FolderNode } from "@/types";
import { api } from "@/lib/api";

const DEFAULT_CONFIG: AppConfig = {
  prowlarr_url: "", prowlarr_api_key: "", tmdb_api_key: "",
  qb_url: "", alist_url: "", alist_token: "",
  scan_paths: [], exclude_dirs: "",
};

export function useLibrary() {
  const [videos, setVideos] = useState<VideoInfo[]>([]);
  const [fileTree, setFileTree] = useState<FolderNode | null>(null);
  const [currentFolder, setCurrentFolder] = useState<FolderNode | null>(null);
  const [config, setConfig] = useState<AppConfig>(DEFAULT_CONFIG);
  const [paths, setPaths] = useState<string[]>([""]);
  const [scanning, setScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState<ScanProgress>({ current: 0, total: 0, lastFile: "" });
  const [loading, setLoading] = useState(true);
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("card");
  const [filterType, setFilterType] = useState<FilterType>("all");
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());

  // 详情抽屉 — 默认展开当前目录
  const [detailTarget, setDetailTarget] = useState<{ type: "folder"; node: FolderNode } | { type: "video"; video: VideoInfo } | null>(null);
  const [detailOpen, setDetailOpen] = useState(true);

  const navHistory = useRef<FolderNode[]>([]);
  const navFuture = useRef<FolderNode[]>([]);

  const findNode = useCallback((node: FolderNode, targetPath: string): FolderNode | null => {
    if (node.path === targetPath) return node;
    for (const child of (node.children || [])) {
      const found = findNode(child, targetPath);
      if (found) return found;
    }
    return null;
  }, []);

  const [refreshKey, setRefreshKey] = useState(0);

  const applyTreeData = useCallback((tData: FolderNode, vData?: VideoInfo[]) => {
    setFileTree(tData);
    setCurrentFolder(prev => {
      if (!prev || prev.path === "") return tData;
      const exact = findNode(tData, prev.path);
      if (exact) return exact;
      const sep = prev.path.includes("/") ? "/" : "\\";
      const parentPath = prev.path.substring(0, prev.path.lastIndexOf(sep));
      if (parentPath) {
        const parent = findNode(tData, parentPath);
        if (parent) {
          if (parent.children?.length === 1) return parent.children[0];
          return parent;
        }
      }
      return tData;
    });
    setDetailTarget(prev => {
      if (!prev) return prev;
      if (prev.type === "folder") {
        const updated = findNode(tData, prev.node.path);
        if (updated) return { type: "folder", node: updated };
        const sep = prev.node.path.includes("/") ? "/" : "\\";
        const parentPath = prev.node.path.substring(0, prev.node.path.lastIndexOf(sep));
        if (parentPath) {
          const parent = findNode(tData, parentPath);
          if (parent?.children?.length === 1) return { type: "folder", node: parent.children[0] };
          if (parent) return { type: "folder", node: parent };
        }
        return prev;
      }
      if (prev.type === "video" && vData) {
        const updated = vData.find(v => v.file_path === prev.video.file_path);
        if (updated) return { type: "video", video: updated };
        const oldFolder = prev.video.folder_name;
        const sameFolder = vData.filter(v => v.folder_name === oldFolder);
        if (sameFolder.length > 0) {
          const oldBase = prev.video.file_name.replace(/\.[^.]+$/, "").substring(0, 10);
          const match = sameFolder.find(v => v.file_name.includes(oldBase));
          if (match) return { type: "video", video: match };
        }
      }
      return prev;
    });
  }, [findNode]);

  const refreshLibrary = useCallback(async () => {
    setRefreshKey(k => k + 1);
    try {
      setLoading(true);
      let vData: VideoInfo[] | undefined;
      let tData: FolderNode | undefined;

      const treeRequest = api.getLibraryTree().then(data => {
        tData = data;
        if (data) applyTreeData(data);
      });
      const libraryRequest = api.getLibrary().then(data => {
        vData = data;
        if (data) setVideos(data);
      });

      await Promise.allSettled([treeRequest, libraryRequest]);
      if (tData && vData) applyTreeData(tData, vData);
      setRefreshKey(k => k + 1);
    } catch {
      setRefreshKey(k => k + 1);
    } finally {
      setLoading(false);
    }
  }, [applyTreeData]);

  const refreshTree = useCallback(async () => {
    setRefreshKey(k => k + 1);
    try {
      const tData = await api.getLibraryTree();
      if (tData) applyTreeData(tData);
    } finally {
      setRefreshKey(k => k + 1);
    }
  }, [applyTreeData]);

  useEffect(() => {
    api.getConfig().then(data => {
      setConfig(data);
      if (data.scan_paths?.length > 0) setPaths(data.scan_paths);
    }).catch(() => {});
    refreshLibrary();
  }, [refreshLibrary]);

  const navigateTo = useCallback((node: FolderNode) => {
    setCurrentFolder(prev => {
      if (prev) navHistory.current.push(prev);
      navFuture.current = [];
      return node;
    });
    // 进入文件夹 = 选中，自动显示该文件夹详情
    setDetailTarget({ type: "folder", node });
    setDetailOpen(true);
  }, []);

  const goBack = useCallback(() => {
    if (navHistory.current.length === 0) return;
    const prev = navHistory.current.pop()!;
    setCurrentFolder(cur => { if (cur) navFuture.current.push(cur); return prev; });
  }, []);
  const goForward = useCallback(() => {
    if (navFuture.current.length === 0) return;
    const next = navFuture.current.pop()!;
    setCurrentFolder(cur => { if (cur) navHistory.current.push(cur); return next; });
  }, []);
  const canGoBack = navHistory.current.length > 0;
  const canGoForward = navFuture.current.length > 0;

  // 初始化不展开详情（根目录）
  useEffect(() => {
    // 不自动展开
  }, [currentFolder]);

  const stats: LibraryStats = useMemo(() => ({
    total: videos.length,
    lowRes: videos.filter(v => v.is_low_res).length,
    missingSub: videos.filter(v => v.subtitle_count === 0).length,
  }), [videos]);

  const filteredVideos = useMemo(() => {
    const base = currentFolder ? currentFolder.videos : [];
    if (filterType === "all") return base;
    if (filterType === "upgrade") return base.filter(v => v.is_low_res);
    if (filterType === "nosub") return base.filter(v => v.subtitle_count === 0);
    if (filterType === "dolby") return base.filter(v => v.audio_codec?.toLowerCase().includes("ac3") || v.audio_codec?.toLowerCase().includes("dts"));
    return base;
  }, [videos, filterType, currentFolder]);

  const groupedVideos = useMemo(() => {
    const sourceVideos = filteredVideos ?? [];
    const groups = sourceVideos.reduce((acc, v) => {
      if (!acc[v.folder_name]) acc[v.folder_name] = [];
      acc[v.folder_name].push(v);
      return acc;
    }, {} as Record<string, VideoInfo[]>);
    const finalGroups: Record<string, VideoInfo[]> = {};
    Object.keys(groups).forEach(key => {
      let prefix = key;
      const matches = key.match(/^(.+?)(?:\s+S\d+|E\d+|\s+\d{4}|\s+\d+)/i);
      if (matches) prefix = matches[1].trim();
      if (!finalGroups[prefix]) finalGroups[prefix] = [];
      finalGroups[prefix].push(...groups[key]);
    });
    return finalGroups;
  }, [filteredVideos]);

  // 扫描：增量追加
  const startScan = useCallback(async (overridePaths?: string[], libraryName?: string) => {
    const scanPaths = overridePaths || paths;
    const controller = new AbortController();
    setAbortController(controller); setScanning(true);
    setScanProgress({ current: 0, total: 0, lastFile: "" });
    const existingPaths = new Set(videos.map(v => v.file_path));
    const accumulated = [...videos];
    try {
      for (const p of scanPaths) {
        if (!p.trim()) continue;
        const response = await api.scan(p.trim(), libraryName, controller.signal);
        // fetch 对 4xx/5xx 不会抛异常，必须显式检查。
        // 漏掉这一步时，错误响应体会被当成 SSE 流去解析，每行都不以 "data: " 开头
        // 于是被静默跳过 —— 表现为进度条一闪而过、什么都没扫、也没有任何报错。
        if (!response.ok) {
          let detail = "";
          try {
            const err = await response.json();
            detail = typeof err?.detail === "string" ? err.detail : "";
          } catch { /* 响应不是 JSON，忽略 */ }
          const reason = detail === "Path does not exist"
            ? `路径不存在：${p.trim()}\n\n服务端访问不到这个目录。如果用 Docker 部署，请确认该目录已挂载进容器，并且容器内路径与这里填写的完全一致。`
            : (detail || `HTTP ${response.status}`);
          throw new Error(reason);
        }
        const reader = response.body?.getReader();
        if (!reader) continue;
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";
          for (const part of parts) {
            if (!part.startsWith("data: ")) continue;
            try {
              const data = JSON.parse(part.replace("data: ", ""));
              if (data.type === "start") setScanProgress(prev => ({ ...prev, total: prev.total + data.total }));
              else if (data.type === "progress") {
                if (data.file && !existingPaths.has(data.file.file_path)) {
                  accumulated.push(data.file); existingPaths.add(data.file.file_path);
                  setVideos([...accumulated]);
                }
                setScanProgress(prev => ({ ...prev, current: prev.current + 1, lastFile: data.file?.file_name || data.raw_file_name }));
              } else if (data.type === "done") {
                // 扫描完成，主动退出循环不等连接关闭
                reader.cancel();
              }
            } catch {}
          }
        }
      }
      setScanning(false);
      refreshLibrary();
    } catch (e: any) {
      // 把真实原因显示出来，而不是笼统的"扫描出错"
      if (e.name !== "AbortError") alert(`扫描失败\n\n${e?.message || e}`);
    } finally { setScanning(false); setAbortController(null); }
  }, [paths, refreshLibrary, videos]);

  const stopScan = useCallback(() => { abortController?.abort(); }, [abortController]);
  const toggleSelect = useCallback((path: string) => {
    setSelectedPaths(prev => { const n = new Set(prev); if (n.has(path)) n.delete(path); else n.add(path); return n; });
  }, []);
  const toggleFolderSelect = useCallback((items: VideoInfo[]) => {
    setSelectedPaths(prev => {
      const n = new Set(prev);
      const all = items.map(v => v.file_path);
      // 始终全选（覆盖），不做反选
      all.forEach(p => n.add(p));
      return n;
    });
  }, []);
  const toggleFolder = useCallback((name: string) => {
    setExpandedFolders(prev => { const n = new Set(prev); if (n.has(name)) n.delete(name); else n.add(name); return n; });
  }, []);
  const batchAction = useCallback(async (action: "delete" | "move" | "copy" | "remove", targetDir?: string) => {
    if (action === "delete" && !confirm("确定要批量删除吗？")) return;
    try { await api.batchManage(action, Array.from(selectedPaths), targetDir); setSelectedPaths(new Set()); refreshLibrary(); } catch { alert("操作失败"); }
  }, [selectedPaths, refreshLibrary]);
  const saveConfig = useCallback(async (newConfig: AppConfig) => {
    const toSave = { ...newConfig, scan_paths: paths };
    await api.saveConfig(toSave); setConfig(toSave);
  }, [paths]);
  const clearSelection = useCallback(() => setSelectedPaths(new Set()), []);

  // 详情操作
  const openFolderDetail = useCallback((node: FolderNode) => { setDetailTarget({ type: "folder", node }); setDetailOpen(true); }, []);
  const openVideoDetail = useCallback((video: VideoInfo) => { setDetailTarget({ type: "video", video }); setDetailOpen(true); }, []);
  const closeDetail = useCallback(() => { setDetailOpen(false); setDetailTarget(null); }, []);

  // 重命名后刷新：关闭详情 → 刷新数据
  const handleRenamed = useCallback(async () => {
    // 重命名后：刷新文件树 + 视频列表（确保展开面板排序更新）
    setRefreshKey(k => k + 1);
    try {
      const [vData, tData] = await Promise.all([api.getLibrary(), api.getLibraryTree()]);
      if (vData) setVideos(vData);
      if (tData) {
        setFileTree(tData);
        setCurrentFolder(prev => {
          if (!prev || prev.path === "") return tData;
          const exact = findNode(tData, prev.path);
          if (exact) return exact;
          // 重命名后路径变了，尝试找父目录
          const sep = prev.path.includes("/") ? "/" : "\\";
          const parentPath = prev.path.substring(0, prev.path.lastIndexOf(sep));
          if (parentPath) {
            const parent = findNode(tData, parentPath);
            if (parent) {
              if (parent.children?.length === 1) return parent.children[0];
              return parent;
            }
          }
          return tData;
        });
        // 同步更新 detailTarget
        setDetailTarget(prev => {
          if (!prev || prev.type !== "folder") return prev;
          const found = findNode(tData, prev.node.path);
          if (found) return { type: "folder", node: found };
          // 路径变了，找父目录下的新节点
          const sep = prev.node.path.includes("/") ? "/" : "\\";
          const parentPath = prev.node.path.substring(0, prev.node.path.lastIndexOf(sep));
          if (parentPath) {
            const parent = findNode(tData, parentPath);
            if (parent?.children?.length) {
              // 找最新的子节点（重命名后的）
              const newest = parent.children.find(c => !findNode(tData, prev.node.path));
              if (newest) return { type: "folder", node: newest };
              return { type: "folder", node: parent.children[0] };
            }
          }
          return prev;
        });
      }
    } catch {}
  }, []);

  // 批处理模式
  const [batchMode, setBatchMode] = useState(false);
  const toggleBatchMode = useCallback(() => {
    setBatchMode(prev => {
      if (prev) setSelectedPaths(new Set()); // 退出时清空选择
      return !prev;
    });
  }, []);

  const invertSelect = useCallback((allPaths: string[]) => {
    setSelectedPaths(prev => {
      const n = new Set(prev);
      allPaths.forEach(p => n.has(p) ? n.delete(p) : n.add(p));
      return n;
    });
  }, []);

  // 当前所在的一级分类标签（从导航历史中查找最近的一级分类目录）
  const currentCategoryTag = useMemo(() => {
    if (!currentFolder) return "";
    // 当前文件夹自身是一级分类
    if (currentFolder.category_tag) return currentFolder.category_tag;
    // 从 parent_category_tag 获取
    if (currentFolder.parent_category_tag) return currentFolder.parent_category_tag;
    // 从导航历史中查找
    for (let i = navHistory.current.length - 1; i >= 0; i--) {
      const h = navHistory.current[i];
      if (h.category_tag) return h.category_tag;
      if (h.parent_category_tag) return h.parent_category_tag;
    }
    return "";
  }, [currentFolder]);

  return {
    videos, fileTree, currentFolder, navigateTo, goBack, goForward, canGoBack, canGoForward,
    config, setConfig, paths, setPaths, scanning, scanProgress, loading,
    viewMode, setViewMode, filterType, setFilterType,
    selectedPaths, expandedFolders, stats, filteredVideos, groupedVideos,
    startScan, stopScan, toggleSelect, toggleFolderSelect, clearSelection, invertSelect,
    toggleFolder, batchAction, saveConfig, refreshLibrary, refreshTree,
    detailTarget, detailOpen, openFolderDetail, openVideoDetail, closeDetail, handleRenamed,
    batchMode, toggleBatchMode, refreshKey, currentCategoryTag,
  };
}
