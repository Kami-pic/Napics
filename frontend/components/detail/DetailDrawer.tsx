// 右侧详情面板
"use client";
import { useState, useEffect, useCallback, useMemo } from "react";
import type { VideoInfo, FolderNode, ScrapeResult, MatchConfidence } from "@/types";
import { api } from "@/lib/api";
import { formatSize, formatDuration, isLeafFolder } from "@/lib/utils";
import { FOLDER_TYPE_LABELS, isAggregate as isAggregateType } from "@/lib/folderTypes";

// 模块级缓存：操作状态不随组件卸载丢失
// key = 路径，value = 各种操作的状态
interface DetailCacheEntry {
  // 一键整理 / 标准结构 / 自动命名等 action 状态
  actionLoading: boolean;
  actionResult: string;
  actionPlan: any;
  abortController: AbortController | null;
  // 刮削状态
  scrapeLoading: boolean;
  scrapeStatus: string;  // "idle" | "loading" | "success" | "failed" | "not_found"
  scrapeData: any;
  // VideoDetail 专用
  renameResult: string;
  structureResult: string;
  // 时间戳
  timestamp: number;
}
const detailCache = new Map<string, Partial<DetailCacheEntry>>();

function getCached(path: string): Partial<DetailCacheEntry> {
  return detailCache.get(path) || {};
}
function setCached(path: string, updates: Partial<DetailCacheEntry>) {
  const prev = detailCache.get(path) || {};
  detailCache.set(path, { ...prev, ...updates, timestamp: Date.now() });
}

interface DetailDrawerProps {
  target: { type: "folder"; node: FolderNode } | { type: "video"; video: VideoInfo } | null;
  open: boolean;
  onClose: () => void;
  onPlay: (path: string) => void;
  onSearch: (query: string, ctx?: any) => void;
  onRefresh: () => void;
  onRenamed: () => void;
  batchMode: boolean;
  selectedPaths: Set<string>;
  batchAction: (action: "delete" | "move" | "remove", targetDir?: string) => void;
  onClearSelection: () => void;
  currentVideos?: VideoInfo[];
  onSelectAll?: () => void;
  onInvertSelect?: () => void;
  currentCategoryTag?: string;
}

export default function DetailDrawer({ target, open, onClose, onPlay, onSearch, onRefresh, onRenamed,
  batchMode, selectedPaths, batchAction, onClearSelection, currentVideos, onSelectAll, onInvertSelect, currentCategoryTag }: DetailDrawerProps) {
  if (!open) return null;
  if (batchMode && selectedPaths.size > 0) {
    return (
      <aside className="w-[380px] h-screen bg-[#141414] border-l border-white/[0.06] flex flex-col flex-shrink-0">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <h3 className="text-base font-semibold text-slate-200">批处理</h3>
          <span className="text-xs text-slate-500">已选 {selectedPaths.size} 项</span>
        </div>
        <BatchPanel selectedPaths={selectedPaths} batchAction={batchAction} onClear={onClearSelection} onSearch={onSearch} onRefresh={onRefresh}
          currentVideos={currentVideos} onSelectAll={onSelectAll} onInvertSelect={onInvertSelect} />
      </aside>
    );
  }
  if (!target) return null;
  // 根目录不显示详情面板
  if (target.type === "folder" && target.node.path === "") return null;
  const currentName = target.type === "folder"
    ? (target.node.name || "媒体库")
    : target.video.file_name;
  const currentPath = target.type === "folder" ? target.node.path : target.video.file_path;

  return (
    <aside data-detail-drawer className="w-[380px] h-screen bg-[#141414] border-l border-white/[0.06] flex flex-col flex-shrink-0">
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06] flex-shrink-0">
        <EditableTitle name={currentName} path={currentPath} onRenamed={onRenamed} />
        <button onClick={onClose} className="w-9 h-9 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition-all flex-shrink-0 text-lg">✕</button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {target.type === "folder" ? (
          <FolderDetail key={target.node.path} node={target.node} onRefresh={onRefresh} onSearch={onSearch} currentCategoryTag={currentCategoryTag || ""} />
        ) : (
          <VideoDetail key={target.video.file_path} video={target.video} onPlay={onPlay} onSearch={onSearch} onRefresh={onRefresh} />
        )}
      </div>
    </aside>
  );
}

// ── 可编辑标题 ──
function EditableTitle({ name, path, onRenamed }: { name: string; path: string; onRenamed: () => void }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(name);
  const [saving, setSaving] = useState(false);

  // name 变化时同步 value
  useEffect(() => {
    setValue(name);
    setEditing(false);
  }, [name, path]);

  const handleSave = async () => {
    const trimmed = value.trim();
    if (!trimmed || trimmed === name) { setEditing(false); return; }
    setSaving(true);
    try {
      await api.rename(path, trimmed);
      onRenamed();
      setEditing(false);
    } catch (e: any) {
      alert("重命名失败: " + (e.message || ""));
    }
    setSaving(false);
  };

  if (editing) {
    return (
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <input value={value} onChange={e => setValue(e.target.value)} autoFocus
          onKeyDown={e => { if (e.key === "Enter") handleSave(); if (e.key === "Escape") { setEditing(false); setValue(name); } }}
          onBlur={() => { setTimeout(() => { setEditing(false); setValue(name); }, 150); }}
          className="flex-1 bg-white/[0.06] border border-white/[0.1] rounded-lg px-3 py-1.5 text-sm text-white outline-none focus:border-blue-500/40 min-w-0" />
        <button onMouseDown={e => e.preventDefault()} onClick={handleSave} disabled={saving} className="text-xs text-blue-400 hover:text-blue-300 flex-shrink-0">{saving ? "..." : "保存"}</button>
        <button onMouseDown={e => e.preventDefault()} onClick={() => { setEditing(false); setValue(name); }} className="text-xs text-slate-500 flex-shrink-0">取消</button>
      </div>
    );
  }

  return (
    <h3 className="text-base font-semibold text-slate-200 truncate pr-3 cursor-pointer hover:text-white group flex items-center gap-2 flex-1 min-w-0"
      onClick={() => setEditing(true)} title="点击重命名">
      <span className="truncate">{name}</span>
      <svg className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400 flex-shrink-0 transition-colors" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
    </h3>
  );
}

// ── 文件夹详情 ──
function FolderDetail({ node, onRefresh, onSearch, currentCategoryTag }: { node: FolderNode; onRefresh: () => void; onSearch: (q: string, ctx?: any) => void; currentCategoryTag: string }) {
  const [actionResult, setActionResult] = useState(() => getCached(node.path).actionResult || "");
  const [actionLoading, setActionLoading] = useState(() => getCached(node.path).actionLoading || false);
  const [lastSnapshotId, setLastSnapshotId] = useState<number | null>(null);
  const [posterKey, setPosterKey] = useState(0);
  const [posterDeleted, setPosterDeleted] = useState(false);
  const [noScrape, setNoScrape] = useState(false);
  const [useAi, setUseAi] = useState(false);
  const [actionPlan, setActionPlan] = useState<any>(() => getCached(node.path).actionPlan || null);
  const [abortController, setAbortController] = useState<AbortController | null>(() => getCached(node.path).abortController || null);
  const [organizeHover, setOrganizeHover] = useState(false);

  // 同步状态到缓存
  useEffect(() => {
    setCached(node.path, {
      actionLoading, actionResult, actionPlan, abortController,
    });
  }, [node.path, actionLoading, actionResult, actionPlan, abortController]);

  // 如果缓存中有正在进行的请求（loading=true 但 controller 已失效），重置状态
  useEffect(() => {
    const cached = getCached(node.path);
    if (cached.actionLoading && !cached.abortController) {
      setActionLoading(false);
    }
  }, [node.path]);
  const totalSize = node.videos.reduce((sum, v) => sum + v.size_gb, 0);
  const isRoot = !node.path || node.path === "";
  const folderType = node.folder_type || "";
  const isAggregate = isAggregateType(folderType) || !!node.is_top_category;
  // 所属一级分类标签：从 currentFolder 传入
  const parentCategoryTag = node.category_tag || currentCategoryTag || 
    ((folderType === "tv" || folderType === "season") ? "tv" : "movie");
  const canScrape = !isRoot && !node.is_top_category && node.name !== "" && !noScrape && !isAggregate;
  // 刮削搜索名：优先用 clean_name（刮削后保存的干净名或清洗后的名字）
  const scrapeName = canScrape 
    ? (node.clean_name || node.videos[0]?.clean_name || node.name)
    : "";
  const { data: scrape, loading: scrapeLoading, status: scrapeStatus, rescrape: _rescrape, reload, setData: setScrapeData, confidence, pendingConfirm, setPendingConfirm } = useScrape(scrapeName, canScrape ? node.path : "", false, folderType === "tv" || folderType === "season");
  const rescrape = async () => { await _rescrape(); setPosterKey(k => k + 1); setPosterDeleted(false); onRefresh(); };

  // 加载禁止刮削状态
  useEffect(() => {
    if (!node.path) return;
    api.getNoScrape().then(list => setNoScrape(list.includes(node.path))).catch(() => {});
  }, [node.path]);
  const toggleNoScrape = async () => {
    const next = !noScrape;
    setNoScrape(next);
    await api.setNoScrape(node.path, next);
  };

  // 当前文件夹的直接视频路径（不递归子文件夹）
  const directVideoPaths = (node.videos || []).map(v => v.file_path);

  // 递归收集所有视频路径（含子文件夹）
  const allVideoPaths = useMemo(() => {
    const paths: string[] = [];
    const collect = (n: FolderNode) => {
      (n.videos || []).forEach(v => paths.push(v.file_path));
      (n.children || []).forEach(c => collect(c));
    };
    collect(node);
    return paths;
  }, [node]);

  // 文件夹级别操作：移动/复制整个文件夹，删除用文件夹路径
  const handleMove = async (t: string) => {
    if (!confirm(`确定要移动文件夹 "${node.name}" 到 ${t}？`)) return;
    try {
      // 移动整个文件夹
      await api.rename(node.path, t + "\\" + node.name);
      onRefresh();
    } catch {
      // fallback: 逐个移动直接视频
      try { await api.batchManage("move", directVideoPaths, t); onRefresh(); } catch { alert("移动失败"); }
    }
  };
  const handleDelete = async () => {
    if (!confirm(`确定要删除文件夹 "${node.name}" 及其所有内容？`)) return;
    try { await api.batchManage("delete", allVideoPaths); onRefresh(); } catch { alert("删除失败"); }
  };
  const handleRemove = async () => { await api.batchManage("remove", allVideoPaths); onRefresh(); };

  const doAction = async (action: string, dryRun: boolean = true) => {
    setActionLoading(true); if (dryRun) setActionResult("");
    try {
      if (action === "supplement") {
        const res = await api.scrapeSupplement(node.path);
        setActionResult(res.status === "supplemented" ? "已补充缺少的字段" : res.status === "complete" ? "数据已完整" : "未找到匹配");
        onRefresh();
      } else if (action === "rename") {
        // 自动命名：预览
        const res = await api.renameVideos(node.path, true);
        const items = res.items || (Array.isArray(res) ? res : []);
        const changed = items.filter((o: any) => !o.unchanged);
        const unchanged = items.filter((o: any) => o.unchanged);
        if (changed.length > 0) {
          const truncName = (n: string) => n.length > 30 ? n.slice(0, 12) + "..." + n.slice(-12) : n;
          let msg = "预览-rename " + changed.length + " 项需要重命名";
          if (unchanged.length > 0) msg += `，${unchanged.length} 项已是标准格式`;
          msg += "\n" + changed.map((o: any) => "• " + truncName(o.old_name || "") + "\n  → " + (o.new_name || "")).join("\n");
          setActionResult(msg);
        } else {
          setActionResult("当前命名已是标准格式，无需修改");
        }
      } else if (action === "rename_shadow") {
        // 更新标准名（只更新标准名，不改原始文件名）
        const res = await api.renameVideos(node.path, false, true);
        setActionResult(`已更新标准名：${res.filled || res.shadow_filled || 0} 项`);
        setTimeout(() => onRefresh(), 300);
      } else if (action === "rename_real") {
        // 替换原始名（真实重命名文件）
        const res = await api.renameVideos(node.path, false, false);
        setLastSnapshotId(res.snapshot_id || null);
        setActionResult("替换原始名完成");
        setTimeout(() => onRefresh(), 300);
      } else if (action === "organize") {
        // V3 一键整理 = 两段式（先推演后执行）
        if (dryRun) {
          // 推演模式：调 /organize/full?dry_run=true（支持中止）
          const ctrl = new AbortController();
          setAbortController(ctrl);
          try {
          const res = await api.fullOrganize(node.path, true, useAi, ctrl.signal);
          const plan = res.plan || [];
          const summary = res.summary || {};
          const tmdbMatch = res.tmdb_match || {};
          const wrapPlan = res.wrap_plan || [];
          const archivePlan = res.archive_plan || [];

          // 保存完整 plan 供确认执行时回传
          setActionPlan({ ...res, folder_type: res.folder_type });

          let msg = "预览-organize";
          if (tmdbMatch.title) {
            msg += `\n🎬 匹配: ${tmdbMatch.title}`;
            if (tmdbMatch.english_title && tmdbMatch.english_title !== tmdbMatch.title) msg += ` (${tmdbMatch.english_title})`;
            msg += `\n来源: ${tmdbMatch.match_source === "existing_nfo" ? "本地 NFO 锁定" : "TMDB 搜索"}`;
          }
          msg += `\n类型: ${res.folder_type || "unknown"}`;
          if (wrapPlan.length) msg += `\n📦 封装: ${wrapPlan.length} 项`;
          if (archivePlan.length) msg += `\n🗑️ 旧刮削清理: ${archivePlan.length} 个目录`;
          if (summary.total_videos) {
            msg += `\n\n📊 视频: ${summary.total_videos} 个`;
            msg += `\n✅ 将处理: ${summary.will_process} 个`;
            if (summary.will_skip) msg += `\n⏭️ 跳过: ${summary.will_skip} 个`;
            if (summary.seasons_to_create?.length) msg += `\n📁 季目录: ${summary.seasons_to_create.join(", ")}`;
          }
          // 显示前几个 plan item
          const showItems = plan.filter((i: any) => !i.skip_reason).slice(0, 5);
          if (showItems.length) {
            msg += "\n";
            showItems.forEach((i: any) => {
              const m = i.mapped ? `S${String(i.mapped.season).padStart(2,"0")}E${String(i.mapped.episode).padStart(2,"0")}` : "?";
              const method = i.parsed?.method === "ai" ? " 🤖" : "";
              msg += `\n• ${i.original_filename} → ${m}${method}`;
            });
            if (plan.filter((i: any) => !i.skip_reason).length > 5) msg += `\n  ... 还有 ${plan.filter((i: any) => !i.skip_reason).length - 5} 项`;
          }
          // 显示跳过的
          const skipped = plan.filter((i: any) => i.skip_reason);
          if (skipped.length) {
            msg += `\n\n⚠️ 跳过 ${skipped.length} 个:`;
            skipped.slice(0, 3).forEach((i: any) => { msg += `\n• ${i.original_filename}: ${i.skip_reason}`; });
            if (skipped.length > 3) msg += `\n  ... 还有 ${skipped.length - 3} 个`;
          }
          setActionResult(summary.will_process > 0 || wrapPlan.length > 0 ? msg : "无需整理");
          } catch (e: any) {
            if (e?.name === 'AbortError') {
              setActionResult("已中止分析");
            } else {
              throw e;  // 让外层 catch 处理
            }
          } finally {
            setAbortController(null);
          }
        } else {
          // 确权执行：回传 action_plan
          if (actionPlan) {
            const res = await api.fullOrganizeExecute(node.path, actionPlan, useAi);
            const steps = res.steps || {};
            let msg = "整理完成";
            if (steps.wrap) msg += `\n封装: ${steps.wrap} 项`;
            if (steps.archive) msg += `\n旧刮削清理: ${steps.archive} 项`;
            if (steps.scrape?.nfo_written) msg += `\n刮削: ${steps.scrape.nfo_written} 个 NFO`;
            if (steps.structure?.moved) msg += `\n结构归位: ${steps.structure.moved} 项`;
            if (steps.shadow) msg += `\n影子名: ${steps.shadow} 项`;
            setActionResult(msg);
            setActionPlan(null);
            onRefresh();
          } else {
            // 无 plan，直接完整执行（兼容）
            const res = await api.fullOrganize(node.path, false, useAi);
            const steps = res.steps || {};
            let msg = "整理完成";
            if (steps.shadow) msg += `\n影子名: ${steps.shadow} 项`;
            setActionResult(msg);
            onRefresh();
          }
        }
      } else if (action === "ai") {
        const s = await api.getAISuggestions();
        setActionResult(s?.length > 0 ? s.length + " 条 AI 建议" : "暂无建议");
      }
    } catch { setActionResult("操作失败"); }
    setActionLoading(false);
  };

  const lastAction = actionResult.split(" ")[0].replace("预览-", "");

  // 构建层级路径：从 node.path 提取最后 2-3 层
  const pathParts = node.path.split(/[\\/]/).filter(Boolean);
  const breadcrumb = pathParts.length > 2 ? pathParts.slice(-2).join(" › ") : pathParts.slice(-1).join("");
  const folderTypeLabel = FOLDER_TYPE_LABELS[folderType] || folderType;

  return (
    <div className="p-5 space-y-4">
      {/* 层级路径指示 */}
      {!isRoot && node.path && (
        <div className="flex items-center gap-1.5 text-[11px] text-slate-500 truncate">
          <span className="shrink-0">{folderType === "season" ? "📂" : folderType === "tv" ? "📺" : folderType === "movie" ? "🎬" : "📁"}</span>
          <span className="truncate">{breadcrumb}</span>
          {folderTypeLabel && <span className="shrink-0 px-1.5 py-0.5 rounded bg-white/[0.06] text-[10px]">{folderTypeLabel}</span>}
        </div>
      )}
      {/* 封面 */}
      {!isRoot && (
        <div className="relative">
          <Poster key={posterKey} fallbackName={node.name} localPath={node.path} posterDeleted={posterDeleted} noScrape={isAggregate} />
          <div className="absolute top-2 right-2 z-10">
            <PosterUpload path={node.path} hideDeleteScrape={isAggregate} onUploaded={(deleted) => { setPosterKey(k => k + 1); if (deleted) { setPosterDeleted(true); if (!isAggregate) setScrapeData(null); } else { setPosterDeleted(false); } if (!isAggregate) reload(); onRefresh(); }} />
          </div>
        </div>
      )}
      {/* 一级分类目录：分类标签选择器 */}
      {(node.is_top_category || node.category_tag) && (
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500">分类标签</span>
          <select value={node.category_tag || "movie"} onChange={async (e) => {
            const newTag = e.target.value;
            try {
              await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/library/category-tag`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({path: node.path, tag: newTag})
              });
              await onRefresh();
            } catch {}
          }} className="text-[11px] px-2 py-0.5 rounded-md font-medium bg-white/[0.06] text-slate-400 border border-white/[0.08] outline-none cursor-pointer">
            {[
              {v: "movie", l: "电影"},
              {v: "tv", l: "剧集"},
            ].map(t => (
              <option key={t.v} value={t.v}>{t.l}</option>
            ))}
          </select>
        </div>
      )}
      {/* 文件夹类型标签（可修改，非一级分类目录） */}
      {folderType && !node.is_top_category && (
        <div className="flex items-center gap-2">
          <select value={folderType} onChange={async (e) => {
            const newType = e.target.value;
            try {
              await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/library/folder-type`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({path: node.path, folder_type: newType})
              });
              await onRefresh();
            } catch {}
          }} className="text-[11px] px-2 py-0.5 rounded-md font-medium bg-white/[0.06] text-slate-400 border border-white/[0.08] outline-none cursor-pointer">
            {(parentCategoryTag === "tv"
              ? ["tv", "season", "mixed"]
              : (() => {
                  const canBeMovie = node.videos.length <= 1 && (!node.children || node.children.length === 0);
                  return canBeMovie ? ["movie", "collection", "series", "mixed"] : ["collection", "series", "mixed"];
                })()
            ).map(t => (
              <option key={t} value={t}>{FOLDER_TYPE_LABELS[t] || t}</option>
            ))}
          </select>
        </div>
      )}
      {/* 刮削内容：只在末端刮削单元（movie/tv/season）时显示 */}
      {!isAggregate && scrapeLoading && <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-blue-500/10 border border-blue-500/20"><div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin flex-shrink-0" /><span className="text-xs text-blue-400">正在刮削...</span></div>}
      {!isAggregate && scrapeStatus === "success" && !scrapeLoading && scrape && scrape.tmdb_id > 0 && <><div className="text-xs text-green-400/70">✓ {scrape.title || "已匹配"}</div><ScrapeInfo data={scrape} /></>}
      {!isAggregate && confidence && <ConfidenceBadge confidence={confidence} pendingConfirm={pendingConfirm} onConfirm={() => setPendingConfirm(false)} onReject={() => { setPendingConfirm(false); }} />}
      {/* movie 类型显示视频级标准名，tv/season 显示文件夹级标准名 */}
      {folderType === "movie" && node.videos[0] && (
        <ShadowNameSection path={node.videos[0].file_path} video={node.videos[0]} onRefresh={onRefresh} />
      )}
      {(folderType === "tv" || folderType === "season") && (
        <ShadowNameSection path={node.path} folderName={node.name} folderShadowName={node.shadow_name} onRefresh={onRefresh} />
      )}
      <div className="grid grid-cols-3 gap-2">
        {[[String(node.video_count), "视频"], [String(node.children?.length || 0), "子目录"], [formatSize(totalSize), "总大小"]].map(([v, l]) => (
          <div key={l} className="bg-white/[0.04] rounded-lg p-2.5 text-center"><p className="text-base font-semibold text-white">{v}</p><p className="text-[11px] text-slate-500">{l}</p></div>
        ))}
      </div>
      {/* 第一行操作按钮 */}
      {(() => {
        // cnName：从 clean_name 提取中文部分
        const cleanName = node.clean_name || node.name;
        const cnParts = cleanName.match(/[\u4e00-\u9fff\u3400-\u4dbf]+/g);
        const cnName = cnParts ? [...new Set(cnParts)].join("") : cleanName;
        // enName：shadow_name 去年份 > clean_name 中的英文部分
        const shadowClean = (node.shadow_name || "").replace(/\s*\(\d{4}\)\s*$/, "").trim();
        // shadow_name 可能含中文，提取纯英文部分
        const shadowEn = shadowClean.replace(/[\u4e00-\u9fff\u3400-\u4dbf]+/g, " ").replace(/\s+/g, " ").trim();
        const enFromClean = cleanName.replace(/[\u4e00-\u9fff\u3400-\u4dbf]+/g, " ").replace(/\s+/g, " ").trim();
        const enName = shadowEn || enFromClean || "";
        const ft = node.folder_type || "";
        // 季号：从 node.name 中提取
        const sMatch = node.name.match(/(?:Season|S)\s*(\d+)/i) || node.name.match(/第(\d+)季/);
        const sNum = sMatch ? parseInt(sMatch[1]) : undefined;
        // 默认搜索词
        const defaultQuery = ft === "season" && sNum
          ? `${cnName} Season ${sNum}`
          : (cnName && enName && cnName !== enName ? `${cnName} ${enName}` : cnName);
        const ctx = { cnName, enName, folderType: ft, seasonNumber: sNum, savePath: node.path };
        return isAggregate ? (
          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => onSearch(defaultQuery, ctx)} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-300">搜索升级</button>
            <button onClick={rescrape} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-300">一键刮削</button>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            <button onClick={() => onSearch(defaultQuery, ctx)} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-300">搜索升级</button>
            <button onClick={rescrape} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-300">一键刮削</button>
            <CandidatePicker name={node.clean_name || node.videos[0]?.clean_name || node.name} path={node.path} onSelected={(d) => { if (d) setScrapeData(d); setPosterKey(k => k + 1); onRefresh(); }} />
          </div>
        );
      })()}
      {/* 第二行：移动到 / 复制到 / 删除 / 移除 */}
      <div className="grid grid-cols-4 gap-2">
        <MoveAction onMove={handleMove} />
        <CopyAction onCopy={async (t) => { try { await api.batchManage("copy", allVideoPaths, t); onRefresh(); } catch { alert("失败"); } }} />
        <DeleteAction onDelete={handleDelete} />
        <button onClick={handleRemove} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.06] text-xs text-slate-500">移除</button>
      </div>
      {/* 第三行：自动命名 / 标准结构 / 一键整理 + AI开关 */}
      <div className="space-y-2">
        <button onClick={() => doAction("rename")} disabled={actionLoading} className="w-full py-2.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-sm text-slate-300 disabled:opacity-50">自动命名</button>
        <button onClick={async () => { setActionLoading(true); setActionResult(""); try { const res = await api.structureOrganize(node.path, true); const ops = res.ops || []; const videoExts = ['.mp4','.mkv','.avi','.rmvb','.rm','.flv','.ts','.m4v','.mov','.wmv']; const videoOps = ops.filter((o: any) => { const p = o.old || o.path || o.desc || ''; return videoExts.some(ext => p.toLowerCase().endsWith(ext)) || o.action === 'rename_dir' || o.action === 'rmdir'; }); const moveOps = videoOps.filter((o: any) => o.action === 'move'); const renameOps = videoOps.filter((o: any) => o.action === 'rename_dir'); if (ops.length) { let msg = `预览-structure ${moveOps.length} 个视频`; if (renameOps.length) msg += `，${renameOps.length} 个目录重命名`; moveOps.slice(0, 8).forEach((o: any) => { msg += `\n📦 ${o.desc || ''}`; }); renameOps.slice(0, 3).forEach((o: any) => { msg += `\n✏️ ${o.desc || ''}`; }); if (moveOps.length > 8) msg += `\n  ... 还有 ${moveOps.length - 8} 个视频`; setActionResult(msg); } else { setActionResult("结构已标准，无需调整"); } } catch (e: any) { setActionResult("操作失败: " + (e?.message || String(e))); } setActionLoading(false); }} disabled={actionLoading} className="w-full py-2.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-sm text-slate-300 disabled:opacity-50">标准结构</button>
        <div className="flex gap-2">
          {actionLoading && abortController ? (
            <button
              onMouseEnter={() => setOrganizeHover(true)} onMouseLeave={() => setOrganizeHover(false)}
              onClick={() => { abortController.abort(); setAbortController(null); setActionLoading(false); }}
              className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${organizeHover ? "bg-red-600/60 text-red-200" : "bg-white/[0.04] text-slate-400"}`}
            >
              {organizeHover ? "⏹ 中止" : <><div className="w-3.5 h-3.5 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />正在分析...</>}
            </button>
          ) : (
            <button onClick={() => doAction("organize")} disabled={actionLoading} className="flex-1 py-2.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-sm text-slate-300 disabled:opacity-50">一键整理</button>
          )}
          <button onClick={() => setUseAi(!useAi)} className={`px-3 py-2.5 rounded-lg text-xs transition-all ${useAi ? "bg-blue-600/60 text-white" : "bg-white/[0.04] text-slate-500 hover:bg-white/[0.06]"}`}>🤖</button>
        </div>
      </div>
      {/* 操作结果 */}
      {actionResult && (
        <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-3 text-xs text-slate-300">
          {actionResult.split("\n").map((line, i) => {
            if (line.startsWith("  → ")) return <div key={i} className="text-blue-400 font-medium mb-1">{line}</div>;
            if (line.startsWith("📦 ")) return <div key={i} className="text-emerald-400/80 mt-1">{line}</div>;
            if (line.startsWith("✏️ ")) return <div key={i} className="text-amber-400/80 mt-1">{line}</div>;
            if (line.startsWith("• ")) return <div key={i} className="text-slate-500 mt-1.5">{line}</div>;
            return <div key={i}>{line}</div>;
          })}
          {actionResult.includes("预览-rename") && (
            <div className="flex gap-2 mt-3">
              <button onClick={() => doAction("rename_shadow", false)} disabled={actionLoading}
                className="flex-1 py-2 rounded-lg bg-blue-600/80 hover:bg-blue-500 text-sm font-medium disabled:opacity-50">更新标准名</button>
              <button onClick={() => doAction("rename_real", false)} disabled={actionLoading}
                className="flex-1 py-2 rounded-lg bg-amber-600/80 hover:bg-amber-500 text-sm font-medium disabled:opacity-50">替换原始名</button>
            </div>
          )}
          {actionResult.startsWith("预览-organize") && (
            <button onClick={() => doAction("organize", false)} disabled={actionLoading}
              className="mt-2 w-full py-2 rounded-lg bg-blue-600/80 hover:bg-blue-500 text-sm font-medium disabled:opacity-50">确认执行</button>
          )}
          {actionResult.startsWith("预览-structure") && (
            <button onClick={async () => { setActionLoading(true); try { const res = await api.structureOrganize(node.path, false); setActionResult("结构整理完成: " + (res.count || 0) + " 项操作"); onRefresh(); } catch (e: any) { setActionResult("执行失败: " + (e?.message || String(e))); } setActionLoading(false); }} disabled={actionLoading}
              className="mt-2 w-full py-2 rounded-lg bg-blue-600/80 hover:bg-blue-500 text-sm font-medium disabled:opacity-50">确认执行</button>
          )}
          {actionResult.startsWith("预览") && !actionResult.includes("预览-rename") && !actionResult.includes("预览-organize") && !actionResult.includes("预览-structure") && (
            <button onClick={() => doAction(lastAction, false)} disabled={actionLoading}
              className="mt-2 w-full py-2 rounded-lg bg-blue-600/80 hover:bg-blue-500 text-sm font-medium disabled:opacity-50">确认执行</button>
          )}
        </div>
      )}
      <InfoRow label="路径" value={node.path} />
      {!isRoot && !isAggregate && (
        <button onClick={toggleNoScrape} className={`w-full py-2 rounded-lg text-xs transition-all ${noScrape ? "bg-red-500/20 text-red-400 border border-red-500/30" : "bg-white/[0.04] text-slate-500 hover:bg-white/[0.06]"}`}>
          {noScrape ? "🚫 已禁止刮削（点击解除）" : "禁止刮削此文件夹"}
        </button>
      )}
    </div>
  );
}

// ── 视频详情 ──
function VideoDetail({ video: v, onPlay, onSearch, onRefresh }: { video: VideoInfo; onPlay: (p: string) => void; onSearch: (q: string, ctx?: any) => void; onRefresh: () => void }) {
  const { data: scrape, loading: scrapeLoading, status: scrapeStatus, rescrape: _rescrape, reload, setData: setScrapeData, confidence, pendingConfirm, setPendingConfirm } = useScrape(v.clean_name || v.file_name, v.file_path, false);
  const rescrape = async () => { await _rescrape(); setPosterKey(k => k + 1); setPosterDeleted(false); onRefresh(); };
  const [posterKey, setPosterKey] = useState(0);
  const [posterDeleted, setPosterDeleted] = useState(false);
  const handleMove = async (t: string) => { try { await api.batchManage("move", [v.file_path], t); onRefresh(); } catch { alert("失败"); } };
  const handleDelete = async () => { try { await api.batchManage("delete", [v.file_path]); onRefresh(); } catch { alert("失败"); } };
  const [renameResult, setRenameResult] = useState(() => getCached(v.file_path).renameResult || "");
  const [renameLoading, setRenameLoading] = useState(false);
  const [structureLoading, setStructureLoading] = useState(false);
  const [structureResult, setStructureResult] = useState(() => getCached(v.file_path).structureResult || "");

  // 同步到缓存
  useEffect(() => {
    setCached(v.file_path, { renameResult, structureResult });
  }, [v.file_path, renameResult, structureResult]);

  // 判断是否已封装：视频所在文件夹只有这一个视频（或少量关联文件）→ 已封装
  // 简单判断：视频的父目录名不是一级分类目录常见名 → 已封装
  const videoDir = v.file_path.replace(/[\\/][^\\/]+$/, '');
  const videoDirName = videoDir.split(/[\\/]/).pop() || "";
  const isLooseVideo = ["电影", "动画电影", "电视剧", "动画番", "其他视频", "综艺", "纪录片"].some(cat => videoDirName.includes(cat));

  const handleStructure = async () => {
    setStructureLoading(true); setStructureResult("");
    try {
      const res = await api.structureOrganize(videoDir, true);
      const ops = res.ops || [];
      const videoExts = ['.mp4','.mkv','.avi','.rmvb','.rm','.flv','.ts','.m4v','.mov','.wmv'];
      const videoOps = ops.filter((o: any) => {
        const p = o.old || o.path || o.desc || '';
        return videoExts.some(ext => p.toLowerCase().endsWith(ext)) || o.action === 'rename_dir';
      });
      const moveOps = videoOps.filter((o: any) => o.action === 'move');
      if (ops.length) {
        let msg = `预览-structure ${moveOps.length} 个视频`;
        moveOps.slice(0, 5).forEach((o: any) => { msg += `\n📦 ${o.desc || ''}`; });
        if (moveOps.length > 5) msg += `\n  ... 还有 ${moveOps.length - 5} 个`;
        setStructureResult(msg);
      } else {
        setStructureResult("结构已标准，无需调整");
      }
    } catch (e: any) { setStructureResult("失败: " + (e?.message || String(e))); }
    setStructureLoading(false);
  };
  const handleAutoRename = async (dryRun: boolean = true, shadowOnly: boolean = false) => {
    setRenameLoading(true);
    if (dryRun) setRenameResult("");
    try {
      const res = await api.renameVideos(v.file_path, dryRun, shadowOnly);
      if (dryRun) {
        const items = res.items || (Array.isArray(res) ? res : []);
        const changed = items.filter((o: any) => !o.unchanged);
        if (changed.length > 0) {
          const truncName = (n: string) => n.length > 30 ? n.slice(0, 12) + "..." + n.slice(-12) : n;
          setRenameResult("预览-rename\n" + changed.map((o: any) => "• " + truncName(o.old_name || "") + "\n  → " + (o.new_name || "")).join("\n"));
        } else {
          setRenameResult(res.message || "当前命名已是标准格式");
        }
      } else {
        setRenameResult(shadowOnly ? `已更新标准名` : "重命名完成");
        // 不调 onRefresh() 避免焦点丢失，延迟刷新
        setTimeout(() => onRefresh(), 500);
      }
    } catch (e: any) { setRenameResult("失败: " + (e?.message || "请检查路径")); }
    setRenameLoading(false);
  };
  const handleSupplement = async () => {
    try {
      const folder = v.file_path.substring(0, v.file_path.lastIndexOf("\\")) || v.file_path.substring(0, v.file_path.lastIndexOf("/"));
      await api.scrapeSupplement(folder);
      onRefresh();
    } catch {}
  };

  return (
    <div className="p-5 space-y-4">
      <div className="relative"><Poster key={posterKey} fallbackName={v.file_name} localPath={v.file_path.replace(/[\\/][^\\/]+$/, '')} aspect="poster" posterDeleted={posterDeleted} /><div className="absolute top-2 right-2 z-10"><PosterUpload path={v.file_path} onUploaded={(deleted) => { setPosterKey(k => k + 1); if (deleted) { setPosterDeleted(true); setScrapeData(null); } else { setPosterDeleted(false); } reload(); onRefresh(); }} /></div></div>
      {scrapeLoading && <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-blue-500/10 border border-blue-500/20"><div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin flex-shrink-0" /><span className="text-xs text-blue-400">正在刮削...</span></div>}
      {scrapeStatus === "success" && !scrapeLoading && scrape && <><div className="text-xs text-green-400/70">✓ {scrape.title || "已匹配"}</div><ScrapeInfo data={scrape} /></>}
      {confidence && <ConfidenceBadge confidence={confidence} pendingConfirm={pendingConfirm} onConfirm={() => setPendingConfirm(false)} onReject={() => { setPendingConfirm(false); }} />}
      <ShadowNameSection path={v.file_path} video={v} onRefresh={onRefresh} />
      {/* 第一行：搜索升级 / 一键刮削 / 重新匹配 */}
      {(() => {
        // 从 clean_name 拆分中英文，英文名优先用 shadow_name（去年份）
        const cleanName = v.clean_name || v.folder_name || v.file_name;
        const cnParts = cleanName.match(/[\u4e00-\u9fff\u3400-\u4dbf]+/g);
        const cnName = cnParts ? [...new Set(cnParts)].join("") : cleanName;
        const shadowClean = (v.shadow_name || "").replace(/\s*\(\d{4}\)\s*$/, "").trim();
        // shadow_name 可能含中文，提取纯英文部分
        const shadowEn = shadowClean.replace(/[\u4e00-\u9fff\u3400-\u4dbf]+/g, " ").replace(/\s+/g, " ").trim();
        const enFromClean = cleanName.replace(/[\u4e00-\u9fff\u3400-\u4dbf]+/g, " ").replace(/\s+/g, " ").trim();
        const enName = shadowEn || enFromClean || "";
        // 从文件名提取季集号
        const seMatch = v.file_name.match(/S(\d+)E(\d+)/i);
        const sNum = seMatch ? parseInt(seMatch[1]) : undefined;
        const eNum = seMatch ? parseInt(seMatch[2]) : undefined;
        const epTag = sNum !== undefined && eNum !== undefined ? `S${String(sNum).padStart(2,"0")}E${String(eNum).padStart(2,"0")}` : undefined;
        // 默认搜索词：集文件用 中文名+SxxExx
        const defaultQuery = epTag ? `${cnName} ${epTag}` : (cnName && enName && cnName !== enName ? `${cnName} ${enName}` : cnName);
        const ctx = { cnName, enName, folderType: "", seasonNumber: sNum, episodeTag: epTag, savePath: v.file_path.replace(/[\\/][^\\/]+$/, '') };
        return (
          <div className="grid grid-cols-3 gap-2">
            <button onClick={() => onSearch(defaultQuery, ctx)} className="py-2 rounded-lg bg-white/[0.06] hover:bg-white/10 text-xs text-slate-300">搜索升级</button>
            <button onClick={rescrape} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-300">一键刮削</button>
            <CandidatePicker name={v.clean_name || v.file_name} path={v.file_path} onSelected={(d) => { if (d) setScrapeData(d); setPosterKey(k => k + 1); onRefresh(); }} />
          </div>
        );
      })()}
      {/* 第二行：移动到 / 复制到 / 删除 / 移除 */}
      <div className="grid grid-cols-4 gap-2">
        <MoveAction onMove={handleMove} />
        <CopyAction onCopy={async (t) => { try { await api.batchManage("copy", [v.file_path], t); onRefresh(); } catch { alert("失败"); } }} />
        <DeleteAction onDelete={handleDelete} />
        <button onClick={async () => { await api.batchManage("remove", [v.file_path]); onRefresh(); }} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.06] text-xs text-slate-500">移除</button>
      </div>
      {/* 第三行：播放 / 标准结构 / 自动重命名 */}
      <div className="space-y-2">
        <button onClick={() => onPlay(v.file_path)} className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-medium flex items-center justify-center gap-1.5"><svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>播放</button>
        <button onClick={handleStructure} disabled={structureLoading || !isLooseVideo} className={`w-full py-2.5 rounded-lg text-sm disabled:opacity-50 ${isLooseVideo ? "bg-white/[0.04] hover:bg-white/[0.08] text-slate-300" : "bg-white/[0.02] text-slate-600 cursor-not-allowed"}`}>{structureLoading ? "处理中..." : isLooseVideo ? "标准结构" : "✓ 已封装"}</button>
        <button onClick={() => handleAutoRename(true)} disabled={renameLoading} className="w-full py-2.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-sm text-slate-300 disabled:opacity-50">{renameLoading ? "处理中..." : "自动重命名"}</button>
      </div>
      {/* 标准结构结果 */}
      {structureResult && (
        <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-3 text-xs text-slate-300">
          {structureResult.split("\n").map((line, i) => {
            if (line.startsWith("• ")) return <div key={i} className="text-slate-500 mt-1">{line}</div>;
            return <div key={i}>{line}</div>;
          })}
          {structureResult.startsWith("预览-structure") && (
            <button onClick={async () => { setStructureLoading(true); try { const res = await api.structureOrganize(videoDir, false); setStructureResult("封装完成: " + (res.count || 0) + " 项"); onRefresh(); } catch (e: any) { setStructureResult("失败: " + (e?.message || String(e))); } setStructureLoading(false); }} disabled={structureLoading}
              className="mt-2 w-full py-2 rounded-lg bg-blue-600/80 hover:bg-blue-500 text-sm font-medium disabled:opacity-50">确认执行</button>
          )}
        </div>
      )}
      {/* 重命名结果 */}
      {renameResult && (
        <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-3 text-xs text-slate-300">
          {renameResult.split("\n").map((line, i) => {
            if (line.startsWith("  → ")) return <div key={i} className="text-blue-400 font-medium mb-1">{line}</div>;
            if (line.startsWith("• ")) return <div key={i} className="text-slate-500 mt-1.5">{line}</div>;
            return <div key={i}>{line}</div>;
          })}
          {renameResult.includes("预览-rename") && (
            <div className="flex gap-2 mt-3">
              <button onClick={() => handleAutoRename(false, false)} disabled={renameLoading}
                className="flex-1 py-2 rounded-lg bg-blue-600/80 hover:bg-blue-500 text-sm font-medium disabled:opacity-50">执行改名</button>
            </div>
          )}
        </div>
      )}
      {/* 文件信息 */}
      <div>
        <h5 className="text-sm font-medium text-slate-300 mb-2">文件信息</h5>
        {[["分辨率", v.resolution, false], ["视频编码", v.video_codec || "—", false], ["音频编码", v.audio_codec || "—", false], ["HDR", v.hdr_type, false], ["大小", formatSize(v.size_gb), false], ["时长", formatDuration(v.duration), false], ["字幕", v.subtitle_count > 0 ? v.subtitle_count + " 条" : "无", false], ["画质", v.is_low_res ? "低画质" : "正常", v.is_low_res], ["路径", v.file_path, false]].map(([label, value, warn]) => (
          <InfoRow key={label as string} label={label as string} value={value as string} warn={warn as boolean} />
        ))}
      </div>
    </div>
  );
}

// ── 通用组件 ──
function Poster({ url, fallbackName, localPath, aspect = "video", posterDeleted = false, noScrape = false }: { url?: string | null; fallbackName: string; localPath?: string; aspect?: "video" | "poster"; posterDeleted?: boolean; noScrape?: boolean }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const [remoteSrc, setRemoteSrc] = useState<string | null>(null);
  const [stage, setStage] = useState<"local" | "remote" | "done">(posterDeleted ? "done" : "local");
  const [cacheBust] = useState(() => Date.now());
  const localSrc = localPath ? api.getLocalPoster(localPath, noScrape) + `&_t=${cacheBust}` : null;
  const src = stage === "local" ? localSrc : stage === "remote" ? remoteSrc : null;
  const cls = aspect === "poster" ? "aspect-[2/3] max-h-[260px] mx-auto" : "aspect-video";
  useEffect(() => { setLoaded(false); setError(false); setRemoteSrc(null); setStage(posterDeleted ? "done" : "local"); }, [localPath, fallbackName, posterDeleted]);
  return (
    <div className={`${cls} rounded-xl overflow-hidden bg-[#222] relative`}>
      {!loaded && !error && stage !== "done" && src && <div className="absolute inset-0 flex items-center justify-center"><div className="w-6 h-6 border-2 border-slate-800 border-t-slate-500 rounded-full animate-spin" /></div>}
      {(stage === "done" || (!src && stage !== "local")) && <div className="absolute inset-0 bg-[#1a1a1a] flex items-center justify-center"><span className="text-slate-700 text-3xl">🎬</span></div>}
      {src && stage !== "done" && <img src={src} alt="" className={`w-full h-full object-cover transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-0"}`}
        onLoad={() => setLoaded(true)}
        onError={() => {
          if (stage === "local" && localPath && !posterDeleted && !noScrape) {
            // 本地封面不存在，尝试从 NFO 读远程封面 URL（仅末端刮削单元）
            setStage("done");
            api.readScrape(localPath, true).then(r => {
              if (r.status === "ok" && r.data?.poster_url) {
                // 通过后端代理加载远程封面（走 HTTP 代理）
                const proxyUrl = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/proxy/image?url=${encodeURIComponent(r.data.poster_url)}`;
                setRemoteSrc(proxyUrl);
                setStage("remote"); setLoaded(false); setError(false);
              }
            }).catch(() => {});
          } else { setStage("done"); }
        }} />}
    </div>
  );
}
function InfoRow({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center justify-between py-2 px-1 border-b border-white/[0.03] cursor-pointer" onClick={() => { navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); }} title="点击复制">
      <span className="text-sm text-slate-500">{label}</span>
      <span className={`text-sm truncate max-w-[200px] text-right ${warn ? "text-orange-400" : "text-slate-300"}`}>{copied ? <span className="text-green-400 text-xs">已复制</span> : value}</span>
    </div>
  );
}
function TipButton({ icon, label, tip, onClick }: { icon: string; label: string; tip: string; onClick?: () => void }) {
  return (
    <button onClick={onClick} className="w-full py-2.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-sm text-slate-300 transition-all text-left px-4 flex items-center gap-2.5 group relative">
      <span>{icon}</span><span>{label}</span>
      <div className="absolute left-0 bottom-full mb-2 px-3 py-2 bg-[#222] border border-white/[0.08] rounded-lg text-xs text-slate-400 w-64 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 shadow-xl">{tip}</div>
    </button>
  );
}
function MoveAction({ onMove }: { onMove: (t: string) => void }) {
  const [show, setShow] = useState(false);
  const [target, setTarget] = useState("");
  if (!show) return <button onClick={() => setShow(true)} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-300">移动到</button>;
  return (<div className="col-span-4 flex gap-2"><input value={target} onChange={e => setTarget(e.target.value)} placeholder="目标路径" autoFocus onBlur={() => setTimeout(() => setShow(false), 150)} className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs outline-none text-slate-300" onKeyDown={e => { if (e.key === "Enter" && target) { onMove(target); setShow(false); } if (e.key === "Escape") setShow(false); }} /><button onMouseDown={e => e.preventDefault()} onClick={() => { if (target) { onMove(target); setShow(false); } }} className="px-3 py-2 rounded-lg bg-blue-500/20 text-blue-400 text-xs">确定</button></div>);
}
function CopyAction({ onCopy }: { onCopy: (t: string) => void }) {
  const [show, setShow] = useState(false);
  const [target, setTarget] = useState("");
  if (!show) return <button onClick={() => setShow(true)} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-300">复制到</button>;
  return (<div className="col-span-4 flex gap-2"><input value={target} onChange={e => setTarget(e.target.value)} placeholder="目标路径" autoFocus onBlur={() => setTimeout(() => setShow(false), 150)} className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs outline-none text-slate-300" onKeyDown={e => { if (e.key === "Enter" && target) { onCopy(target); setShow(false); } if (e.key === "Escape") setShow(false); }} /><button onMouseDown={e => e.preventDefault()} onClick={() => { if (target) { onCopy(target); setShow(false); } }} className="px-3 py-2 rounded-lg bg-blue-500/20 text-blue-400 text-xs">确定</button></div>);
}
function DeleteAction({ onDelete }: { onDelete: () => void }) {
  const [confirm, setConfirm] = useState(false);
  useEffect(() => { if (confirm) { const t = setTimeout(() => setConfirm(false), 3000); return () => clearTimeout(t); } }, [confirm]);
  if (!confirm) return <button onClick={() => setConfirm(true)} className="py-2 rounded-lg bg-white/[0.04] hover:bg-red-500/10 text-xs text-red-400">删除</button>;
  return (<div className="col-span-4 flex items-center gap-2 bg-red-500/5 border border-red-500/20 rounded-lg p-2.5"><span className="text-xs text-red-400 flex-1">确定删除？</span><button onClick={() => { onDelete(); setConfirm(false); }} className="px-3 py-1 rounded bg-red-600 text-white text-xs">删除</button><button onClick={() => setConfirm(false)} className="px-2 py-1 text-xs text-slate-500">取消</button></div>);
}
function CandidatePicker({ name, path, onSelected }: { name: string; path: string; onSelected: (data?: any) => void }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"tmdb" | "douban" | "bangumi">("tmdb");
  const [candidates, setCandidates] = useState<any[]>([]);
  const [doubanCandidates, setDoubanCandidates] = useState<any[]>([]);
  const [bangumiCandidates, setBangumiCandidates] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selecting, setSelecting] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const searchTmdb = async (q?: string) => {
    setLoading(true);
    try { const r = await api.scrapeCandidates(q || searchQuery || name); setCandidates(r.candidates || []); } catch { setCandidates([]); }
    setLoading(false);
  };
  const searchDouban = async (q?: string) => {
    setLoading(true);
    try { const r = await api.scrapeDoubanCandidates(q || searchQuery || name); setDoubanCandidates(r.candidates || []); } catch { setDoubanCandidates([]); }
    setLoading(false);
  };
  const searchBangumi = async (q?: string) => {
    setLoading(true);
    try { const r = await api.scrapeBangumiCandidates(q || searchQuery || name); setBangumiCandidates(r.candidates || []); } catch { setBangumiCandidates([]); }
    setLoading(false);
  };

  const openPanel = async () => {
    setOpen(true); setTab("tmdb"); setSearchQuery(name);
    setLoading(true);
    try { const r = await api.scrapeCandidates(name); setCandidates(r.candidates || []); if (r.query) setSearchQuery(r.query); } catch { setCandidates([]); }
    setLoading(false);
  };
  const switchTab = async (t: "tmdb" | "douban" | "bangumi") => {
    setTab(t);
    const q = searchQuery || name;
    if (t === "douban" && doubanCandidates.length === 0) await searchDouban(q);
    if (t === "tmdb" && candidates.length === 0) await searchTmdb(q);
    if (t === "bangumi" && bangumiCandidates.length === 0) await searchBangumi(q);
  };
  const reSearch = async () => {
    const q = searchQuery.trim();
    if (!q) return;
    // 清空所有 tab 的缓存，强制用新搜索词
    setCandidates([]); setDoubanCandidates([]); setBangumiCandidates([]);
    if (tab === "tmdb") await searchTmdb(q);
    else if (tab === "douban") await searchDouban(q);
    else await searchBangumi(q);
  };

  const selectTmdb = async (c: any) => {
    setSelecting(`tmdb-${c.tmdb_id}`);
    try { const r = await api.scrapeSelect(path, c.tmdb_id, c.media_type); setOpen(false); onSelected(r.data); } catch (e: any) { alert("写入失败: " + (e?.message || e)); }
    setSelecting(null);
  };
  const selectDouban = async (c: any) => {
    setSelecting(`douban-${c.douban_id}`);
    try { const r = await api.scrapeDoubanSelect(path, c.douban_id, c.title, c.year, c.poster_url_original || c.poster_url, c.subtitle); setOpen(false); onSelected(r.data); } catch (e: any) { alert("写入失败: " + (e?.message || e)); }
    setSelecting(null);
  };
  const selectBangumi = async (c: any) => {
    setSelecting(`bgm-${c.bgm_id}`);
    try { const r = await api.scrapeBangumiSelect(path, c.bgm_id); setOpen(false); onSelected(r.data); } catch (e: any) { alert("写入失败: " + (e?.message || e)); }
    setSelecting(null);
  };

  if (!open) return <button onClick={openPanel} className="py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-xs text-amber-400">重新匹配</button>;

  const currentList = tab === "tmdb" ? candidates : tab === "douban" ? doubanCandidates : bangumiCandidates;

  return (
    <div className="col-span-full bg-[#141414] border border-white/[0.06] rounded-xl p-3 space-y-2">
      <div className="flex gap-2">
        <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === "Enter" && reSearch()}
          placeholder="编辑搜索词..."
          className="flex-1 bg-white/[0.06] border border-white/[0.06] rounded-lg px-2.5 py-1.5 text-xs text-white outline-none focus:border-blue-500/40" />
        <button onClick={reSearch} className="px-3 py-1.5 rounded-lg bg-blue-500/20 text-xs text-blue-400 hover:bg-blue-500/30">搜索</button>
        <button onClick={() => setOpen(false)} className="px-2 py-1.5 text-xs text-slate-600 hover:text-slate-400">✕</button>
      </div>
      <div className="flex gap-2">
          <button onClick={() => switchTab("tmdb")} className={`text-xs px-2.5 py-1 rounded-md transition-all ${tab === "tmdb" ? "bg-blue-500/20 text-blue-400" : "text-slate-500 hover:text-slate-300"}`}>TMDB</button>
          <button onClick={() => switchTab("douban")} className={`text-xs px-2.5 py-1 rounded-md transition-all ${tab === "douban" ? "bg-green-500/20 text-green-400" : "text-slate-500 hover:text-slate-300"}`}>豆瓣</button>
          <button onClick={() => switchTab("bangumi")} className={`text-xs px-2.5 py-1 rounded-md transition-all ${tab === "bangumi" ? "bg-pink-500/20 text-pink-400" : "text-slate-500 hover:text-slate-300"}`}>Bangumi</button>
      </div>
      {loading && <div className="flex justify-center py-4"><div className="w-5 h-5 border-2 border-slate-700 border-t-blue-400 rounded-full animate-spin" /></div>}
      {!loading && currentList.length === 0 && <p className="text-xs text-slate-600 py-2">未找到候选</p>}
      <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
        {tab === "tmdb" && candidates.map(c => (
          <button key={`tmdb-${c.tmdb_id}`} onClick={() => selectTmdb(c)} disabled={selecting !== null}
            className={`w-full flex gap-2.5 p-2 rounded-lg text-left transition-all ${selecting === `tmdb-${c.tmdb_id}` ? "bg-blue-500/20 border border-blue-500/30" : "bg-white/[0.03] hover:bg-white/[0.06] border border-transparent"}`}>
            {c.poster_url ? <img src={c.poster_url} alt="" className="w-10 h-14 rounded object-cover flex-shrink-0" /> : <div className="w-10 h-14 rounded bg-[#222] flex-shrink-0" />}
            <div className="flex-1 min-w-0">
              <p className="text-sm text-white truncate">{c.title}</p>
              {c.english_title && c.english_title !== c.title && <p className="text-[11px] text-blue-400/70 truncate">{c.english_title}</p>}
              {c.original_title && c.original_title !== c.title && c.original_title !== c.english_title && <p className="text-[11px] text-slate-500 truncate">{c.original_title}</p>}
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[10px] text-slate-600">{c.year}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${c.media_type === "movie" ? "bg-blue-500/20 text-blue-400" : "bg-green-500/20 text-green-400"}`}>{c.media_type === "movie" ? "电影" : "剧集"}</span>
              </div>
              {c.overview && <p className="text-[11px] text-slate-600 mt-1 line-clamp-2">{c.overview}</p>}
            </div>
          </button>
        ))}
        {tab === "douban" && doubanCandidates.map(c => (
          <button key={`db-${c.douban_id}`} onClick={() => selectDouban(c)} disabled={selecting !== null}
            className={`w-full flex gap-2.5 p-2 rounded-lg text-left transition-all ${selecting === `douban-${c.douban_id}` ? "bg-green-500/20 border border-green-500/30" : "bg-white/[0.03] hover:bg-white/[0.06] border border-transparent"}`}>
            {c.poster_url ? <img src={c.poster_url.startsWith("/") ? `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${c.poster_url}` : c.poster_url} alt="" referrerPolicy="no-referrer" className="w-10 h-14 rounded object-cover flex-shrink-0" /> : <div className="w-10 h-14 rounded bg-[#222] flex-shrink-0" />}
            <div className="flex-1 min-w-0">
              <p className="text-sm text-white truncate">{c.title}</p>
              {c.subtitle && <p className="text-[11px] text-slate-500 truncate">{c.subtitle}</p>}
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[10px] text-slate-600">{c.year}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">{c.episode ? `剧集 ${c.episode}集` : "电影"}</span>
              </div>
            </div>
          </button>
        ))}
        {tab === "bangumi" && bangumiCandidates.map(c => (
          <button key={`bgm-${c.bgm_id}`} onClick={() => selectBangumi(c)} disabled={selecting !== null}
            className={`w-full flex gap-2.5 p-2 rounded-lg text-left transition-all ${selecting === `bgm-${c.bgm_id}` ? "bg-pink-500/20 border border-pink-500/30" : "bg-white/[0.03] hover:bg-white/[0.06] border border-transparent"}`}>
            {c.poster_url ? <img src={c.poster_url} alt="" referrerPolicy="no-referrer" className="w-10 h-14 rounded object-cover flex-shrink-0" /> : <div className="w-10 h-14 rounded bg-[#222] flex-shrink-0" />}
            <div className="flex-1 min-w-0">
              <p className="text-sm text-white truncate">{c.title}</p>
              {c.original_title && c.original_title !== c.title && <p className="text-[11px] text-slate-500 truncate">{c.original_title}</p>}
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[10px] text-slate-600">{c.year}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-pink-500/20 text-pink-400">{c.type}</span>
                {c.rating > 0 && <span className="text-[10px] text-amber-400">★ {c.rating}</span>}
              </div>
              {c.summary && <p className="text-[11px] text-slate-600 mt-1 line-clamp-2">{c.summary}</p>}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
// ── 置信度展示 ──
function ConfidenceBadge({ confidence, pendingConfirm, onConfirm, onReject }: {
  confidence: MatchConfidence | null;
  pendingConfirm: boolean;
  onConfirm: () => void;
  onReject: () => void;
}) {
  if (!confidence) return null;
  const { level, score, details } = confidence;
  const colors = { high: "text-green-400 bg-green-500/10 border-green-500/20", medium: "text-amber-400 bg-amber-500/10 border-amber-500/20", low: "text-red-400 bg-red-500/10 border-red-500/20" };
  const labels = { high: "高置信度", medium: "中置信度", low: "低置信度" };

  return (
    <div className={`rounded-lg border p-2.5 space-y-2 ${colors[level]}`}>
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium">{labels[level]} ({score}分)</span>
        {level === "high" && <span className="text-[10px]">✓ 自动采用</span>}
      </div>
      {details && Object.keys(details).length > 0 && (
        <div className="flex flex-wrap gap-1">
          {Object.entries(details).map(([k, v]) => (
            <span key={k} className="text-[9px] px-1.5 py-0.5 rounded bg-white/[0.04]">{k}: {v > 0 ? "+" : ""}{v}</span>
          ))}
        </div>
      )}
      {level === "medium" && pendingConfirm && (
        <div className="flex gap-2 pt-1">
          <button onClick={onConfirm} className="flex-1 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-xs text-amber-400 font-medium">确认采用</button>
          <button onClick={onReject} className="px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.06] text-xs text-slate-500">重新匹配</button>
        </div>
      )}
      {level === "low" && pendingConfirm && (
        <div className="pt-1">
          <p className="text-[10px] mb-1.5">置信度较低，建议手动选择匹配</p>
          <button onClick={onReject} className="w-full py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.06] text-xs text-slate-400">打开候选列表</button>
        </div>
      )}
    </div>
  );
}
// ── 原始文件名展示区（只读） ──
function ShadowNameSection({ path, video, folderName, folderShadowName, onRefresh }: { path: string; video?: VideoInfo; folderName?: string; folderShadowName?: string; onRefresh?: () => void }) {
  // 文件夹模式：用 folderName/folderShadowName；视频模式：用 video 字段
  const isFolder = !video && !!folderName;
  const fileName = video?.file_name || folderName || "";
  const shadowName = video?.shadow_name || folderShadowName || "";
  const cleanName = video?.clean_name || "";
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [editingClean, setEditingClean] = useState(false);
  const [cleanEditValue, setCleanEditValue] = useState("");

  useEffect(() => { setEditing(false); setEditingClean(false); }, [path, video?.file_name]);

  if (!fileName) return null;

  const handleRename = async (newName: string) => {
    if (!newName.trim() || newName.trim() === fileName) { setEditing(false); return; }
    setSaving(true);
    try {
      if (isFolder) {
        // 文件夹重命名：path 的最后一段替换为新名字
        const parentDir = path.substring(0, path.lastIndexOf("\\")) || path.substring(0, path.lastIndexOf("/"));
        const newPath = parentDir + "\\" + newName.trim();
        await api.rename(path, newPath);
      } else {
        await api.rename(path, newName.trim());
      }
      setEditing(false);
      onRefresh?.();
    } catch (e: any) { alert("重命名失败: " + (e?.message || "")); }
    setSaving(false);
  };

  const handleApplyShadow = async () => {
    if (!shadowName) return;
    if (isFolder) {
      // 文件夹：用标准名替换文件夹名
      if (!confirm(`确定用标准名替换文件夹名？\n\n${fileName}\n→ ${shadowName}`)) return;
      await handleRename(shadowName);
    } else {
      const ext = fileName.includes(".") ? fileName.substring(fileName.lastIndexOf(".")) : "";
      const newName = shadowName + ext;
      if (!confirm(`确定用标准名替换原始文件名？\n\n${fileName}\n→ ${newName}`)) return;
      await handleRename(newName);
    }
  };

  const handleSaveShadow = async (newShadow: string) => {
    if (!newShadow.trim()) { setEditing(false); return; }
    setSaving(true);
    try {
      if (isFolder) {
        // 文件夹标准名：通过 shadow-name API 保存（用 path 作为 key）
        await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/media/shadow-name`, {
          method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({file_path: path, shadow_name: newShadow.trim(), source: "manual"})
        });
      } else if (video?.file_path) {
        await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/media/shadow-name`, {
          method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({file_path: video.file_path, shadow_name: newShadow.trim(), source: "manual"})
        });
      }
      setEditing(false);
      onRefresh?.();
    } catch (e: any) { alert("保存标准名失败: " + (e?.message || "")); }
    setSaving(false);
  };

  const handleSaveClean = async (newClean: string) => {
    if (!newClean.trim() || !video?.file_path) { setEditingClean(false); return; }
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/library/clean-name`, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({file_path: video.file_path, clean_name: newClean.trim()})
      });
      setEditingClean(false);
      onRefresh?.();
    } catch { alert("保存失败"); }
  };

  if (editing) {
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-1.5 px-1">
          <span className="text-[10px] text-slate-600 flex-shrink-0">✨</span>
          <input value={editValue} onChange={e => setEditValue(e.target.value)} autoFocus
            onKeyDown={e => { if (e.key === "Enter") handleSaveShadow(editValue); if (e.key === "Escape") setEditing(false); }}
            onBlur={() => { setTimeout(() => setEditing(false), 150); }}
            className="flex-1 bg-white/[0.06] border border-white/[0.08] rounded px-2 py-0.5 text-xs text-white outline-none focus:border-blue-500/40 min-w-0"
            placeholder="输入标准名" />
          <button onMouseDown={e => e.preventDefault()} onClick={() => handleSaveShadow(editValue)} disabled={saving} className="text-[10px] text-blue-400 flex-shrink-0">{saving ? "..." : "保存"}</button>
          <button onClick={() => setEditing(false)} className="text-[10px] text-slate-600 flex-shrink-0">取消</button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {/* 标准名 */}
      <div className="flex items-center gap-2 px-1">
        <span className="text-[10px] text-slate-600">✨</span>
        {shadowName ? (
          <>
            <span className="text-xs text-slate-400 truncate flex-1 cursor-pointer hover:text-slate-300"
              onClick={() => { setEditValue(shadowName); setEditing(true); }} title="点击编辑标准名">{shadowName}</span>
            {shadowName !== (isFolder ? fileName : fileName.replace(/\.[^.]+$/, '')) && (
              <button onClick={handleApplyShadow} className="text-[10px] text-amber-500/70 hover:text-amber-400 flex-shrink-0" title="用标准名替换原始名">替换原始名</button>
            )}
          </>
        ) : (
          <span className="text-xs text-slate-600 truncate flex-1 cursor-pointer hover:text-slate-400"
            onClick={() => { setEditValue(fileName.replace(/\.[^.]+$/, '')); setEditing(true); }} title="点击设置标准名">{fileName}</span>
        )}
      </div>
      {/* 清洗名 */}
      <div className="flex items-center gap-2 px-1">
        <span className="text-[10px] text-slate-600">🧹</span>
        {cleanName ? (
          editingClean ? (
            <div className="flex items-center gap-1.5 flex-1">
              <input value={cleanEditValue} onChange={e => setCleanEditValue(e.target.value)} autoFocus
                onKeyDown={e => { if (e.key === "Enter") handleSaveClean(cleanEditValue); if (e.key === "Escape") setEditingClean(false); }}
                onBlur={() => setTimeout(() => setEditingClean(false), 150)}
                className="flex-1 bg-white/[0.06] border border-white/[0.08] rounded px-2 py-0.5 text-[11px] text-white outline-none focus:border-blue-500/40 min-w-0" />
              <button onMouseDown={e => e.preventDefault()} onClick={() => handleSaveClean(cleanEditValue)} className="text-[10px] text-blue-400 flex-shrink-0">保存</button>
            </div>
          ) : (
            <span className="text-[11px] text-slate-600 truncate flex-1 cursor-pointer hover:text-slate-400"
              onClick={() => { setCleanEditValue(cleanName); setEditingClean(true); }} title="点击编辑清洗名">{cleanName}</span>
          )
        ) : (
          <span className="text-[11px] text-slate-600 truncate flex-1">未设置</span>
        )}
      </div>
    </div>
  );
}
function ScrapeInfo({ data }: { data: ScrapeResult }) {
  if (!data.tmdb_id) return null;
  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-center gap-2">{data.year && <span className="text-xs text-slate-500">{data.year}</span>}{data.rating > 0 && <span className="text-xs text-amber-400">★ {data.rating}</span>}{data.media_type === "tv" && data.status && <span className={`text-[10px] px-1.5 py-0.5 rounded ${data.status === "Ended" ? "bg-slate-700 text-slate-400" : "bg-green-500/20 text-green-400"}`}>{data.status === "Ended" ? "已完结" : "连载中"}</span>}</div>
        {data.english_title && data.english_title !== data.title && <p className="text-xs text-blue-400/70 mt-1">{data.english_title}</p>}
        {data.original_title && data.original_title !== data.title && data.original_title !== data.english_title && <p className="text-xs text-slate-600 mt-0.5">{data.original_title}</p>}
      </div>
      {data.genres?.length > 0 && <div className="flex flex-wrap gap-1.5">{data.genres.map(g => <span key={g} className="text-[11px] px-2 py-0.5 rounded-md bg-white/[0.04] text-slate-400">{g}</span>)}</div>}
      {data.overview && <p className="text-sm text-slate-400 leading-relaxed">{data.overview}</p>}
      {data.media_type === "movie" && <div className="space-y-1">{data.director && <InfoRow label="导演" value={data.director} />}{data.cast?.length > 0 && <InfoRow label="主演" value={data.cast.join(" / ")} />}{data.runtime > 0 && <InfoRow label="时长" value={data.runtime + " 分钟"} />}</div>}
      {data.media_type === "tv" && data.total_seasons > 0 && <InfoRow label="总季数" value={data.total_seasons + " 季"} />}
    </div>
  );
}
function useScrape(name: string, path: string, autoScrape: boolean = false, noFallback: boolean = false) {
  const cacheKey = path || name;
  const cached = getCached(cacheKey);
  const [data, setData] = useState<ScrapeResult | null>(cached.scrapeData || null);
  const [loading, setLoading] = useState(false);
  const [scrapeLoading, setScrapeLoading] = useState(cached.scrapeLoading || false);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "failed" | "not_found">(
    (cached.scrapeStatus as any) || "idle"
  );
  const [confidence, setConfidence] = useState<MatchConfidence | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState(false);

  // 同步刮削状态到缓存
  useEffect(() => {
    if (cacheKey) {
      setCached(cacheKey, { scrapeLoading, scrapeStatus: status, scrapeData: data });
    }
  }, [cacheKey, scrapeLoading, status, data]);

  // 恢复时：如果缓存显示 loading 但实际请求已丢失，重置
  useEffect(() => {
    if (cached.scrapeLoading && !scrapeLoading) {
      // 缓存说在 loading 但当前 hook 不是 loading → 可能是恢复后的状态
      // 保持 loading 状态，等请求自然完成或超时
    }
  }, [cacheKey]);

  const reload = useCallback((): Promise<void> => {
    if (!path) return Promise.resolve();
    return api.readScrape(path, noFallback).then(r => {
      if (r.status === "ok" && r.data?.tmdb_id) { setData(r.data); setStatus("success"); }
      else { setData(null); setStatus("not_found"); }
    }).catch(() => { setData(null); setStatus("failed"); });
  }, [path]);

  useEffect(() => {
    if (!name && !path) return;
    let cancelled = false;
    // 如果缓存中有有效数据，直接用缓存
    const c = getCached(path || name);
    if (c.scrapeData?.tmdb_id) {
      setData(c.scrapeData); setStatus("success");
      return;
    }
    if (c.scrapeLoading) {
      // 缓存说正在刮削，保持 loading 状态
      setScrapeLoading(true); setStatus("loading");
      return;
    }
    // 重置状态（path 变化时清除旧数据）
    setData(null); setStatus("idle"); setConfidence(null); setPendingConfirm(false);

    (async () => {
      try {
        if (path) {
          const r = await api.readScrape(path, noFallback);
          if (cancelled) return;
          if (r.status === "ok" && r.data?.tmdb_id) {
            setData(r.data); setStatus("success");
            return;
          }
        }
        if (!cancelled) { setStatus("idle"); }
      } catch {
        if (!cancelled) setStatus("failed");
      }
    })();

    return () => { cancelled = true; };
  }, [name, path]);

  const rescrape = (): Promise<void> => {
    if (!path && !name) return Promise.resolve();
    setScrapeLoading(true); setStatus("loading"); setConfidence(null); setPendingConfirm(false);
    return api.executeScrape(path || name).then(r => {
      const d = r.self?.data || r.data;
      const conf = r.self?.confidence || r.confidence;
      if (conf) setConfidence(conf);
      if (d?.tmdb_id) {
        if (conf?.level === "medium") {
          setData(d); setStatus("success"); setPendingConfirm(true);
        } else if (conf?.level === "low") {
          setData(d); setStatus("success"); setPendingConfirm(true);
        } else {
          setData(d); setStatus("success");
        }
      } else {
        setStatus("not_found");
        // 刮削失败时保留已有数据，但提示用户
        alert("自动刮削未匹配到结果，请尝试「重新匹配」手动选择");
      }
    }).catch(() => { setStatus("failed"); alert("刮削请求失败"); }).finally(() => setScrapeLoading(false));
  };

  return { data, loading: scrapeLoading, status, rescrape, reload, setData, confidence, pendingConfirm, setPendingConfirm };
}
function PosterUpload({ path, onUploaded, hideDeleteScrape = false }: { path: string; onUploaded: (deleted?: boolean) => void; hideDeleteScrape?: boolean }) {
  const [showInput, setShowInput] = useState(false);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!url.trim()) return;
    setLoading(true);
    try {
      await api.setPosterFromUrl(path, url.trim(), hideDeleteScrape);
      setUrl(""); setShowInput(false); onUploaded(false);
    } catch { alert("拉取失败"); }
    setLoading(false);
  };

  const handleDeletePoster = async () => {
    try {
      const res = await api.deletePoster(path);
      onUploaded(true);
    } catch { alert("删除失败"); }
  };

  const handleDeleteScrape = async () => {
    if (!confirm("确定删除刮削数据（NFO+封面）？")) return;
    try { await api.deleteScrape(path); onUploaded(true); } catch { alert("删除失败"); }
  };

  if (showInput) {
    return (
      <div className="flex flex-col gap-1.5 bg-black/60 backdrop-blur rounded-lg p-2 min-w-[200px]">
        <input value={url} onChange={e => setUrl(e.target.value)} placeholder="输入图片 URL"
          onKeyDown={e => e.key === "Enter" && handleSubmit()}
          className="bg-white/10 border border-white/10 rounded px-2 py-1 text-xs text-white outline-none focus:border-blue-500/50 w-full" autoFocus />
        <div className="flex gap-1.5">
          <button onClick={handleSubmit} disabled={loading} className="flex-1 py-1 rounded bg-blue-600/80 text-xs text-white disabled:opacity-50">{loading ? "..." : "确定"}</button>
          <button onClick={() => setShowInput(false)} className="flex-1 py-1 rounded bg-white/10 text-xs text-slate-400">取消</button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-1.5">
      <button onClick={() => setShowInput(true)} className="text-xs text-blue-400 hover:text-blue-300 bg-black/40 backdrop-blur rounded px-2 py-1">换封面</button>
      <button onClick={handleDeletePoster} className="text-xs text-red-400 hover:text-red-300 bg-black/40 backdrop-blur rounded px-2 py-1">删封面</button>
      {!hideDeleteScrape && <button onClick={handleDeleteScrape} className="text-xs text-orange-400 hover:text-orange-300 bg-black/40 backdrop-blur rounded px-2 py-1">删刮削</button>}
    </div>
  );
}
function BatchPanel({ selectedPaths, batchAction, onClear, onSearch, onRefresh, currentVideos, onSelectAll, onInvertSelect }: { selectedPaths: Set<string>; batchAction: (a: "delete" | "move" | "remove", t?: string) => void; onClear: () => void; onSearch: (q: string) => void; onRefresh: () => void; currentVideos?: VideoInfo[]; onSelectAll?: () => void; onInvertSelect?: () => void }) {
  const [moveTarget, setMoveTarget] = useState("");
  const [copyTarget, setCopyTarget] = useState("");
  const [confirmDel, setConfirmDel] = useState(false);
  const [batchLoading, setBatchLoading] = useState("");
  const paths = Array.from(selectedPaths);

  const handleBatchScrape = async () => {
    setBatchLoading("刮削中...");
    try {
      for (let i = 0; i < paths.length; i++) {
        setBatchLoading(`刮削 (${i + 1}/${paths.length})`);
        try { await api.executeScrape(paths[i]); } catch {}
      }
      onRefresh();
    } catch {}
    setBatchLoading("");
  };

  const handleBatchRename = async (shadowOnly: boolean = true) => {
    const label = shadowOnly ? "生成标准名" : "覆盖文件名";
    if (!shadowOnly && !confirm("确定要将标准名覆盖为真实文件名吗？")) return;
    setBatchLoading(`${label}中...`);
    try {
      const folders = new Set<string>();
      for (const fp of paths) {
        const sep = fp.lastIndexOf("\\") !== -1 ? "\\" : "/";
        folders.add(fp.substring(0, fp.lastIndexOf(sep)));
      }
      for (const folder of folders) {
        await api.renameVideos(folder, false, shadowOnly);
      }
      onRefresh();
    } catch {}
    setBatchLoading("");
  };

  return (
    <div className="flex-1 overflow-y-auto p-5 space-y-5">
      <div className="space-y-1 max-h-[200px] overflow-y-auto">{paths.map((p, i) => <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.02] text-xs"><span className="text-slate-500 w-5">{i + 1}</span><span className="text-slate-300 truncate flex-1">{p.split(/[\\/]/).pop()}</span></div>)}</div>
      {batchLoading && (
        <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
          <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
          <span className="text-xs text-blue-400">{batchLoading}</span>
        </div>
      )}
      <div className="space-y-2">
        <div className="flex gap-2"><input value={moveTarget} onChange={e => setMoveTarget(e.target.value)} placeholder="移动目标路径" className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs outline-none text-slate-400" /><button onClick={() => { if (moveTarget) batchAction("move", moveTarget); }} className="px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 text-xs font-medium">移动</button></div>
        <div className="flex gap-2"><input value={copyTarget} onChange={e => setCopyTarget(e.target.value)} placeholder="复制目标路径" className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs outline-none text-slate-400" /><button onClick={async () => { if (copyTarget) { try { await api.batchManage("copy", paths, copyTarget); onRefresh(); } catch { alert("复制失败"); } } }} className="px-4 py-2 rounded-lg bg-cyan-500/20 text-cyan-400 text-xs font-medium">复制</button></div>
        <div className="grid grid-cols-2 gap-2">
          <button onClick={handleBatchScrape} disabled={!!batchLoading} className="py-2 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-xs text-purple-400 disabled:opacity-50">批量刮削</button>
          <button onClick={() => handleBatchRename(true)} disabled={!!batchLoading} className="py-2 rounded-lg bg-green-500/20 hover:bg-green-500/30 text-xs text-green-400 disabled:opacity-50">生成标准名</button>
        </div>
        <button onClick={() => handleBatchRename(false)} disabled={!!batchLoading} className="w-full py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-xs text-amber-400 disabled:opacity-50">标准名覆盖真名</button>
        {!confirmDel ? <button onClick={() => setConfirmDel(true)} className="w-full py-2.5 rounded-lg bg-white/[0.04] hover:bg-red-500/10 text-sm text-red-400">删除</button> : <div className="flex items-center gap-2 bg-red-500/5 border border-red-500/20 rounded-lg p-2.5"><span className="text-xs text-red-400 flex-1">确定删除？</span><button onClick={() => { batchAction("delete"); setConfirmDel(false); }} className="px-3 py-1 rounded bg-red-600 text-white text-xs">删除</button><button onClick={() => setConfirmDel(false)} className="px-2 py-1 text-xs text-slate-500">取消</button></div>}
        <button onClick={() => batchAction("remove")} className="w-full py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.06] text-sm text-slate-500">从媒体库中移除</button>
        <div className="flex gap-2">
          {onSelectAll && <button onClick={onSelectAll} className="flex-1 py-2 text-xs text-slate-500 hover:text-slate-300 bg-white/[0.04] rounded-lg">全选</button>}
          {onInvertSelect && <button onClick={onInvertSelect} className="flex-1 py-2 text-xs text-slate-500 hover:text-slate-300 bg-white/[0.04] rounded-lg">反选</button>}
          <button onClick={onClear} className="flex-1 py-2 text-xs text-slate-500 hover:text-slate-300 bg-white/[0.04] rounded-lg">清空</button>
        </div>
      </div>
    </div>
  );
}
