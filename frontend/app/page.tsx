"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useLibrary } from "@/hooks/useLibrary";
import { useScrollDamping } from "@/hooks/useScrollDamping";
import Header from "@/components/layout/Header";
import Toolbar from "@/components/layout/Toolbar";
import SettingsModal from "@/components/settings/SettingsModal";
import SearchModal from "@/components/search/SearchModal";
import AddMediaPanel from "@/components/media/AddMediaPanel";
import BatchUpgradePanel from "@/components/search/BatchUpgradePanel";
import DiscoverPage from "@/components/media/DiscoverPage";
import CardGrid from "@/components/media/CardGrid";
import FolderTable from "@/components/media/FolderTable";
import Sidebar from "@/components/layout/Sidebar";
import Breadcrumbs from "@/components/layout/Breadcrumbs";
import DetailDrawer from "@/components/detail/DetailDrawer";
import AnalysisReport from "@/components/media/AnalysisReport";
import OperationHistory from "@/components/media/OperationHistory";
import OrganizeProgress from "@/components/media/OrganizeProgress";
import DownloadManagerPanel from "@/components/download/DownloadManagerPanel";
import { api } from "@/lib/api";
import type { VideoInfo, FolderNode } from "@/types";

export default function Home() {
  const {
    videos, fileTree, currentFolder, navigateTo, goBack, goForward, canGoBack, canGoForward,
    config, setConfig, paths, setPaths, scanning, scanProgress, loading,
    viewMode, setViewMode,
    selectedPaths, stats, filteredVideos, groupedVideos,
    startScan, stopScan, toggleSelect, toggleFolderSelect, clearSelection, invertSelect,
    batchAction, saveConfig, refreshLibrary,
    detailTarget, detailOpen, openFolderDetail, openVideoDetail, closeDetail, handleRenamed,
    batchMode, toggleBatchMode, refreshKey, currentCategoryTag,
  } = useLibrary();

  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const discoverRef = useRef<HTMLDivElement>(null);
  const libraryContentRef = useRef<HTMLDivElement>(null);
  const [discoverVisible, setDiscoverVisible] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [searchContext, setSearchContext] = useState<{
    shadowName?: string; cleanName?: string; mediaType?: string;
    cnName?: string; enName?: string; folderType?: string;
    seasonNumber?: number; episodeTag?: string; savePath?: string;
  }>({});
  const [showAddMedia, setShowAddMedia] = useState(false);
  const [showBatchUpgrade, setShowBatchUpgrade] = useState(false);
  const [addMediaQuery, setAddMediaQuery] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [showOrganizeProgress, setShowOrganizeProgress] = useState(false);
  const [organizeTargetPath, setOrganizeTargetPath] = useState("");
  const [showDownloadManager, setShowDownloadManager] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [syncMsg, setSyncMsg] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [syncDone, setSyncDone] = useState(false);

  useEffect(() => {
    const hasPath = paths.some(p => p.trim() !== "");
    if (!hasPath && stats.total === 0 && !scanning) {
      const timer = setTimeout(() => setShowSettings(true), 500);
      return () => clearTimeout(timer);
    }
  }, [paths, stats.total, scanning]);

  useEffect(() => {
    if (!currentFolder || currentFolder.path === "") closeDetail();
  }, [currentFolder]);

  const handlePlay = (path: string) => api.play(path).catch(() => alert("启动播放器失败"));
  const handleOpenSearch = (query: string, ctx?: { shadowName?: string; cleanName?: string; mediaType?: string; cnName?: string; enName?: string; folderType?: string; seasonNumber?: number; episodeTag?: string; savePath?: string }) => {
    setSearchQuery(query);
    setSearchContext(ctx || {});
    setShowSearch(true);
  };
  const handleSelectDoubanMedia = (item: any) => {
    let searchName = "";
    if (item._tmdb_original_title && /[a-zA-Z]/.test(item._tmdb_original_title)) {
      searchName = item._tmdb_original_title;
    }
    if (!searchName && item.subtitle && /[a-zA-Z]/.test(item.subtitle)) {
      searchName = item.subtitle;
    }
    if (!searchName) searchName = item.title || "";
    setAddMediaQuery(searchName);
    setShowAddMedia(true);
  };

  // 从发现页跳转到本地媒体库目录
  const handleNavigateToLocal = useCallback((folderPath: string) => {
    if (!folderPath || !fileTree) return;
    // folderPath 格式如 "动画电影\你的名字。 Your Name. (2016) 1080p"
    const parts = folderPath.replace(/\//g, "\\").split("\\").filter(Boolean);
    let current: FolderNode | undefined;
    let nodes = fileTree.children || [];
    for (const part of parts) {
      current = nodes.find((n: FolderNode) => n.name === part);
      if (!current) break;
      nodes = current.children || [];
    }
    if (current) {
      navigateTo(current);
      // 滚动到顶部
      if (scrollContainerRef.current) scrollContainerRef.current.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [fileTree, navigateTo, scrollContainerRef]);

  // 监听下载面板的"查看"按钮事件
  useEffect(() => {
    const handler = (e: Event) => {
      const folderPath = (e as CustomEvent).detail;
      if (folderPath) handleNavigateToLocal(folderPath);
    };
    window.addEventListener("navigate-to-folder", handler);
    return () => window.removeEventListener("navigate-to-folder", handler);
  }, [handleNavigateToLocal]);

  const currentVideoResolution = detailTarget?.type === "video" ? detailTarget.video.resolution : undefined;
  const qbConfigured = !!config.qb_url;
  const alistConfigured = !!config.alist_url && !!config.alist_token;
  const showDiscover = !currentFolder || currentFolder.path === "";

  const handleStartScan = () => {
    const hasPath = paths.some(p => p.trim() !== "");
    if (!hasPath) { setShowSettings(true); return; }
    startScan();
  };

  // ── 发现区域懒加载：IntersectionObserver 检测进入视口 ──
  useEffect(() => {
    if (!showDiscover || !discoverRef.current) { setDiscoverVisible(false); return; }
    const observer = new IntersectionObserver(
      ([entry]) => setDiscoverVisible(entry.isIntersecting),
      { threshold: 0.05 }
    );
    observer.observe(discoverRef.current);
    return () => observer.disconnect();
  }, [showDiscover]);

  // ── 阻尼 + 磁力吸附 ──
  useScrollDamping({
    containerRef: scrollContainerRef,
    wallRef: discoverRef,
    enabled: showDiscover,
  });

  // ── 键盘拦截：发现页内 Home/PageUp 先回发现页顶部 ──
  useEffect(() => {
    if (!showDiscover || !discoverRef.current || !scrollContainerRef.current) return;
    const container = scrollContainerRef.current;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (!discoverRef.current) return;
      const discoverTop = discoverRef.current.offsetTop;
      const scrollTop = container.scrollTop;
      if (scrollTop < discoverTop - 20) return;

      if (e.key === "Home" && scrollTop > discoverTop + 10) {
        e.preventDefault();
        container.scrollTo({ top: discoverTop - 8, behavior: "smooth" });
      }
      if (e.key === "PageUp" && scrollTop > discoverTop + 10) {
        e.preventDefault();
        const target = Math.max(scrollTop - container.clientHeight, discoverTop - 8);
        container.scrollTo({ top: target, behavior: "smooth" });
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [showDiscover]);

  return (
    <main className="min-h-screen bg-[#0f0f0f] text-white font-sans flex overflow-hidden">
      <Sidebar tree={fileTree} currentFolder={currentFolder} onNavigate={navigateTo}
        collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} />

      <div ref={scrollContainerRef} className="flex-1 h-screen overflow-y-auto no-scrollbar" onClick={(e) => {
        const target = e.target as HTMLElement;
        if (target.closest('[data-card]') || target.closest('[data-expand-panel]') ||
            target.closest('[data-discover-card]') || target.closest('[data-detail-drawer]') ||
            target.closest('button') || target.closest('input') || target.closest('textarea') ||
            target.closest('a') || target.closest('label') || target.closest('tr') ||
            target.closest('table') || target.closest('.fixed') || target.closest('aside') ||
            target.closest('select')) {
          return;
        }
        if (currentFolder && currentFolder.path !== "") openFolderDetail(currentFolder);
        else closeDetail();
      }}>
        <div className="max-w-[1400px] mx-auto px-6 py-4 pb-32">
          {/* 第一排：标题+统计 | 下载管理、扫描、表单管理、设置 */}
          <Header stats={stats} onOpenSettings={() => setShowSettings(true)}
            scanning={scanning} onStartScan={handleStartScan} onStopScan={stopScan}
            onNavigateHome={() => { navigateTo(null as any); if (fileTree) navigateTo(fileTree); }}
            onOpenDownloads={() => setShowDownloadManager(true)}
            syncMsg={syncMsg} syncing={syncing} />

          {/* 第二排：面包屑 | 撤回操作、快速同步、批处理、视图切换 */}
          <div className="flex items-center justify-between mt-2 mb-5">
            <Breadcrumbs currentFolder={currentFolder} tree={fileTree} onNavigate={navigateTo} />
            <Toolbar viewMode={viewMode} setViewMode={setViewMode}
              batchMode={batchMode} onToggleBatch={toggleBatchMode}
              onRefresh={refreshLibrary}
              onOpenHistory={() => setShowHistory(true)}
              onOpenReport={() => setShowReport(true)}
              syncing={syncing} setSyncing={setSyncing}
              syncMsg={syncMsg} setSyncMsg={setSyncMsg}
              syncDone={syncDone} setSyncDone={setSyncDone} />
          </div>

          <div ref={libraryContentRef}>
            {loading && stats.total === 0 ? (
              <div className="flex flex-col items-center justify-center min-h-[50vh] text-center">
                <div className="w-10 h-10 border-3 border-slate-700 border-t-blue-500 rounded-full animate-spin mb-4" />
                <p className="text-slate-500 text-sm">加载媒体库...</p>
              </div>
            ) : stats.total === 0 && !scanning ? (
              <div className="flex flex-col items-center justify-center min-h-[50vh] text-center">
                <span className="text-6xl mb-5 opacity-20">📂</span>
                <p className="text-base font-medium text-slate-400 mb-2">媒体库为空</p>
                <p className="text-sm text-slate-600 mb-6">配置 NAS 路径后点击扫描开始</p>
                <div className="flex gap-3">
                  <button onClick={() => setShowSettings(true)} className="px-5 py-2.5 bg-white/[0.06] border border-white/[0.06] rounded-xl text-sm text-slate-300 hover:bg-white/10 transition-all">设置</button>
                  <button onClick={handleStartScan} className="px-5 py-2.5 bg-blue-600 rounded-xl text-sm text-white hover:bg-blue-500 transition-all">扫描媒体库</button>
                </div>
              </div>
            ) : (
              <>
                {viewMode === "card" && (
                  <CardGrid currentFolder={currentFolder} groupedVideos={groupedVideos}
                    selectedPaths={selectedPaths} batchMode={batchMode} refreshKey={refreshKey}
                    onToggleSelect={toggleSelect} onToggleFolderSelect={toggleFolderSelect}
                    onPlay={handlePlay} onSearch={handleOpenSearch} onNavigate={navigateTo}
                    onVideoDetail={openVideoDetail} onFolderDetail={openFolderDetail} />
                )}
                {viewMode === "list" && (
                  <FolderTable currentFolder={currentFolder} selectedPaths={selectedPaths}
                    onToggleSelect={toggleSelect} onPlay={handlePlay} onSearch={handleOpenSearch}
                    onNavigate={navigateTo} onVideoDetail={openVideoDetail} onFolderDetail={openFolderDetail}
                    batchMode={batchMode} />
                )}
              </>
            )}
          </div>

          {/* 发现区域：根目录时显示，滚动到此处时懒加载 */}
          {showDiscover && (
            <div ref={discoverRef} className="min-h-[200px] mt-10">
              <DiscoverPage onSelectMedia={handleSelectDoubanMedia} onNavigateToLocal={handleNavigateToLocal} visible={discoverVisible} scrollContainerRef={scrollContainerRef} defaultSavePath={config.nas_paths?.[0] || config.nas_path || ""} />
            </div>
          )}
        </div>
      </div>

      <DetailDrawer target={detailTarget} open={detailOpen} onClose={closeDetail}
        onPlay={handlePlay} onSearch={handleOpenSearch} onRefresh={refreshLibrary} onRenamed={handleRenamed}
        batchMode={batchMode} selectedPaths={selectedPaths} batchAction={batchAction} onClearSelection={clearSelection}
        currentVideos={currentFolder?.videos}
        onSelectAll={() => {
          if (!currentFolder) return;
          const all: VideoInfo[] = [...(currentFolder.videos || [])];
          (currentFolder.children || []).forEach(child => all.push(...(child.videos || [])));
          toggleFolderSelect(all);
        }}
        onInvertSelect={() => {
          if (!currentFolder) return;
          const all: string[] = [];
          (currentFolder.videos || []).forEach(v => all.push(v.file_path));
          (currentFolder.children || []).forEach(child => (child.videos || []).forEach(v => all.push(v.file_path)));
          invertSelect(all);
        }}
        currentCategoryTag={currentCategoryTag}
      />

      <SettingsModal open={showSettings} config={config} onSave={saveConfig}
        onClose={() => setShowSettings(false)} setConfig={setConfig} paths={paths} setPaths={setPaths} />
      <SearchModal open={showSearch} query={searchQuery} onClose={() => setShowSearch(false)}
        defaultSavePath={searchContext.savePath || currentFolder?.path || config.nas_paths?.[0] || config.nas_path || ""}
        currentResolution={currentVideoResolution}
        qbConfigured={qbConfigured} alistConfigured={alistConfigured}
        shadowName={searchContext.shadowName} cleanName={searchContext.cleanName}
        mediaType={searchContext.mediaType}
        cnName={searchContext.cnName} enName={searchContext.enName}
        folderType={searchContext.folderType} seasonNumber={searchContext.seasonNumber}
        episodeTag={searchContext.episodeTag} />

      <AddMediaPanel open={showAddMedia} onClose={() => setShowAddMedia(false)}
        onRefresh={refreshLibrary} defaultSavePath={config.nas_paths?.[0] || config.nas_path || ""}
        qbConfigured={qbConfigured} alistConfigured={alistConfigured} initialQuery={addMediaQuery} />

      <BatchUpgradePanel open={showBatchUpgrade} onClose={() => setShowBatchUpgrade(false)}
        items={videos.filter(v => selectedPaths.has(v.file_path)).map(v => ({
          name: v.folder_name || v.file_name,
          path: v.file_path,
          currentResolution: v.resolution || (v.height >= 2160 ? "2160p" : v.height >= 1080 ? "1080p" : v.height >= 720 ? "720p" : "SD"),
        }))}
        qbConfigured={qbConfigured} alistConfigured={alistConfigured} />

      <OperationHistory open={showHistory} onClose={() => setShowHistory(false)} onRefresh={refreshLibrary} />

      <AnalysisReport open={showReport} onClose={() => setShowReport(false)} />

      <OrganizeProgress
        open={showOrganizeProgress}
        path={organizeTargetPath}
        onClose={() => setShowOrganizeProgress(false)}
        onComplete={refreshLibrary}
      />

      <DownloadManagerPanel open={showDownloadManager} onClose={() => setShowDownloadManager(false)} />

      {batchMode && selectedPaths.size > 0 && (
        <div className="fixed bottom-6 right-6 z-40">
          <button onClick={() => setShowBatchUpgrade(true)}
            className="px-5 py-3 bg-blue-600 hover:bg-blue-500 rounded-xl text-sm font-bold shadow-2xl transition-all flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>
            批量搜索升级 ({selectedPaths.size})
          </button>
        </div>
      )}

      {scanning && (
        <div className="fixed bottom-6 left-6 bg-[#1a1a1a] border border-white/[0.06] px-5 py-3.5 rounded-xl shadow-2xl z-50 flex items-center gap-4 animate-in slide-in-from-left duration-300">
          <div className="relative w-11 h-11 flex items-center justify-center">
            <svg className="w-full h-full -rotate-90">
              <circle cx="22" cy="22" r="18" stroke="currentColor" strokeWidth="3" fill="transparent" className="text-slate-800" />
              <circle cx="22" cy="22" r="18" stroke="currentColor" strokeWidth="3" fill="transparent" className="text-blue-500 transition-all duration-300"
                strokeDasharray={`${2 * Math.PI * 18}`} strokeDashoffset={`${2 * Math.PI * 18 * (1 - (scanProgress.current / (scanProgress.total || 1)))}`} />
            </svg>
            <span className="absolute text-[10px] font-medium text-slate-300">{Math.round((scanProgress.current / (scanProgress.total || 1)) * 100)}%</span>
          </div>
          <div>
            <p className="text-xs text-slate-400">{scanProgress.current} / {scanProgress.total}</p>
            <p className="text-xs text-slate-500 truncate max-w-[200px]">{scanProgress.lastFile}</p>
          </div>
          <button onClick={stopScan} className="text-xs text-red-400 hover:text-red-300 ml-2">停止</button>
        </div>
      )}
    </main>
  );
}
