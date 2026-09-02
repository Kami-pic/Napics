// 文件夹详情面板：展示文件夹信息、刮削状态、操作按钮
"use client";
import { useState, useEffect, useMemo } from "react";
import type { FolderNode } from "@/types";
import { api } from "@/lib/api";
import { BASE_URL } from "@/lib/api/base";
import { formatSize, sumFolderSize } from "@/lib/utils";
import { FOLDER_TYPE_LABELS, isAggregate as isAggregateType } from "@/lib/folderTypes";
import { getCached, setCached } from "./detailCache";
import { useScrape } from "./useScrape";
import { Poster, InfoRow, MoveAction, CopyAction, DeleteAction, ConfidenceBadge, ScrapeInfo, ActionButton } from "./DetailComponents";
import { CandidatePicker } from "./CandidatePicker";
import { ShadowNameSection } from "./ShadowNameSection";
import { PosterUpload } from "./PosterUpload";
import { CompletenessBar } from "./CompletenessBar";
import FeatureTip from "@/components/media/FeatureTip";

export function FolderDetail({ node, onRefresh, onTreeRefresh, onSearch, currentCategoryTag }: { node: FolderNode; onRefresh: () => void; onTreeRefresh?: () => void; onSearch: (q: string, ctx?: any) => void; currentCategoryTag: string }) {
  const [actionResult, setActionResult] = useState(() => getCached(node.path).actionResult || "");
  const [actionLoading, setActionLoading] = useState(() => getCached(node.path).actionLoading || false);
  const [generatingIndex, setGeneratingIndex] = useState(false);
  const [shadowNameLoading, setShadowNameLoading] = useState(false);
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
  // 递归含子目录。原来只加当前层的 videos，而 video_count 是递归的 ——
  // 于是「视频 12 个 / 总大小 1.2G」这种自相矛盾的组合很常见。
  const totalSize = sumFolderSize(node);
  const isRoot = !node.path || node.path === "";
  const folderType = node.folder_type || "";
  const isAggregate = isAggregateType(folderType) || !!node.is_top_category;
  // 所属一级分类标签：从 currentFolder 传入
  const parentCategoryTag = node.category_tag || currentCategoryTag || 
    ((folderType === "tv" || folderType === "season") ? "tv" : "movie");
  const canScrape = !isRoot && !node.is_top_category && node.name !== "" && !noScrape && !isAggregate;
  const refreshFolderTree = () => (onTreeRefresh || onRefresh)();
  // 刮削搜索名：优先用 clean_name（刮削后保存的干净名或清洗后的名字）
  const scrapeName = canScrape 
    ? (node.clean_name || node.videos[0]?.clean_name || node.name)
    : "";
  const { data: scrape, loading: scrapeLoading, status: scrapeStatus, rescrape: _rescrape, reload, setData: setScrapeData, confidence, pendingConfirm, setPendingConfirm } = useScrape(scrapeName, canScrape ? node.path : "", false, folderType === "tv" || folderType === "season");
  const rescrape = async () => { await _rescrape(); setPosterKey(k => k + 1); setPosterDeleted(false); refreshFolderTree(); };

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
      await api.batchManage("move", [node.path], t);
      onRefresh();
    } catch {
      alert("移动失败");
    }
  };
  const handleDelete = async () => {
    if (!confirm(`确定要删除文件夹 "${node.name}" 及其所有内容？`)) return;
    try { await api.batchManage("delete", [node.path]); onRefresh(); } catch { alert("删除失败"); }
  };
  const handleRemove = async () => { await api.batchManage("remove", allVideoPaths); onRefresh(); };

  // 生成检索名：movie 文件夹落到视频条目，tv/season 按文件夹批量重算
  const handleGenerateIndexName = async () => {
    const isMovieFolder = folderType === "movie" && !!node.videos[0];
    const targetPath = isMovieFolder ? node.videos[0].file_path : node.path;
    if (!targetPath) return;
    setGeneratingIndex(true);
    try {
      const res = await api.generateCleanName(targetPath, !isMovieFolder);
      if (res.status !== "ok") { setActionResult(res.message || "未能解析出名称，请手动填写检索名"); return; }
      setActionResult(`检索名已更新：${res.cn || ""} ${res.en || ""}`.trim());
      refreshFolderTree();
    } catch (e: any) { setActionResult("生成检索名失败: " + (e?.message || String(e))); }
    setGeneratingIndex(false);
  };

  // 生成标准名：只写影子名，不动磁盘文件名（与「自动重命名」不是一回事）
  const handleGenerateShadowName = async () => {
    if (!node.path) return;
    setShadowNameLoading(true);
    setActionResult("");
    try {
      const res = await api.renameVideos(node.path, false, true);
      setActionResult(`标准名已生成：${res.filled ?? 0}/${res.total ?? node.videos.length} 个视频`);
      refreshFolderTree();
    } catch (e: any) { setActionResult("生成标准名失败: " + (e?.message || String(e))); }
    setShadowNameLoading(false);
  };

  // 标准结构预览（原先是一段内联 handler，抽出来便于复用按钮组件）
  const handleStructurePreview = async () => {
    setActionLoading(true);
    setActionResult("");
    try {
      const res = await api.structureOrganize(node.path, true);
      const ops = res.ops || [];
      const videoExts = ['.mp4','.mkv','.avi','.rmvb','.rm','.flv','.ts','.m4v','.mov','.wmv'];
      const videoOps = ops.filter((o: any) => {
        const p = o.old || o.path || o.desc || '';
        return videoExts.some(ext => p.toLowerCase().endsWith(ext)) || o.action === 'rename_dir' || o.action === 'rmdir';
      });
      const moveOps = videoOps.filter((o: any) => o.action === 'move');
      const renameOps = videoOps.filter((o: any) => o.action === 'rename_dir');
      if (ops.length) {
        let msg = `预览-structure ${moveOps.length} 个视频`;
        if (renameOps.length) msg += `，${renameOps.length} 个目录重命名`;
        moveOps.slice(0, 8).forEach((o: any) => { msg += `\n📦 ${o.desc || ''}`; });
        renameOps.slice(0, 3).forEach((o: any) => { msg += `\n✏️ ${o.desc || ''}`; });
        if (moveOps.length > 8) msg += `\n  ... 还有 ${moveOps.length - 8} 个视频`;
        setActionResult(msg);
      } else {
        setActionResult("结构已标准，无需调整");
      }
    } catch (e: any) {
      setActionResult("操作失败: " + (e?.message || String(e)));
    }
    setActionLoading(false);
  };

  const doAction = async (action: string, dryRun: boolean = true) => {
    setActionLoading(true); if (dryRun) setActionResult("");
    try {
      if (action === "supplement") {
        const res = await api.scrapeSupplement(node.path);
        setActionResult(res.status === "supplemented" ? "已补充缺少的字段" : res.status === "complete" ? "数据已完整" : "未找到匹配");
        onRefresh();
      } else if (action === "rename_shadow") {
        if (dryRun) {
          // 预览模式：显示将要重命名的文件
          const res = await api.renameVideos(node.path, true);
          const items = res.items || (Array.isArray(res) ? res : []);
          const changed = items.filter((o: any) => !o.unchanged);
          if (changed.length > 0) {
            const truncName = (n: string) => n.length > 30 ? n.slice(0, 12) + "..." + n.slice(-12) : n;
            let msg = `预览-rename_shadow ${changed.length} 项将重命名`;
            msg += "\n" + changed.slice(0, 8).map((o: any) => "• " + truncName(o.old_name || "") + "\n  → " + (o.new_name || "")).join("\n");
            if (changed.length > 8) msg += `\n  ... 还有 ${changed.length - 8} 项`;
            setActionResult(msg);
          } else {
            setActionResult("当前命名已是标准格式，无需修改");
          }
        } else {
          // 执行模式：物理重命名（带二次确认）
          if (!confirm("确定要重命名这些文件？此操作会修改物理文件名。")) {
            setActionLoading(false);
            return;
          }
          const res = await api.renameVideos(node.path, false, false);
          setActionResult(`重命名完成：${res.items?.filter((o: any) => !o.unchanged).length || 0} 项`);
          setTimeout(() => onRefresh(), 300);
        }
      } else if (action === "organize") {
        // V3 一键整理 = 两段式（先推演后执行）
        if (dryRun) {
          const ctrl = new AbortController();
          setAbortController(ctrl);
          try {
          const res = await api.fullOrganize(node.path, true, useAi, ctrl.signal);
          const plan = res.plan || [];
          const summary = res.summary || {};
          const tmdbMatch = res.tmdb_match || {};
          const wrapPlan = res.wrap_plan || [];
          const archivePlan = res.archive_plan || [];
          setActionPlan({ ...res, folder_type: res.folder_type });
          let msg = "预览-organize";
          if (tmdbMatch.title) {
            msg += `\n🎬 匹配: ${tmdbMatch.title}`;
            if (tmdbMatch.english_title && tmdbMatch.english_title !== tmdbMatch.title) msg += ` (${tmdbMatch.english_title})`;
            msg += `\n来源: ${tmdbMatch.match_source === "existing_nfo" ? "本地 NFO 锁定" : "TMDB 搜索"}`;
          }
          msg += `\n类型: ${res.folder_type || "unknown"}`;
          if (wrapPlan.length) msg += `\n📦 封装: ${wrapPlan.length} 项`;
          if (archivePlan.length) msg += `\n🗑️ 旧数据清理: ${archivePlan.length} 个目录`;
          if (summary.total_videos) {
            msg += `\n\n📊 视频: ${summary.total_videos} 个`;
            msg += `\n✅ 将处理: ${summary.will_process} 个`;
            if (summary.will_skip) msg += `\n⏭️ 跳过: ${summary.will_skip} 个`;
            if (summary.seasons_to_create?.length) msg += `\n📁 季目录: ${summary.seasons_to_create.join(", ")}`;
          }
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
              throw e;
            }
          } finally {
            setAbortController(null);
          }
        } else {
          if (actionPlan) {
            const res = await api.fullOrganizeExecute(node.path, actionPlan, useAi);
            const steps = res.steps || {};
            let msg = "整理完成";
            if (steps.wrap) msg += `\n封装: ${steps.wrap} 项`;
            if (steps.archive) msg += `\n旧数据清理: ${steps.archive} 项`;
            if (steps.scrape?.nfo_written) msg += `\n识别: ${steps.scrape.nfo_written} 个 NFO`;
            if (steps.structure?.moved) msg += `\n结构归位: ${steps.structure.moved} 项`;
            if (steps.shadow) msg += `\n标准化名称: ${steps.shadow} 项`;
            setActionResult(msg);
            setActionPlan(null);
            onRefresh();
          } else {
            const res = await api.fullOrganize(node.path, false, useAi);
            const steps = res.steps || {};
            let msg = "整理完成";
            if (steps.shadow) msg += `\n标准化名称: ${steps.shadow} 项`;
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
            <PosterUpload path={node.path} hideDeleteScrape={isAggregate} onUploaded={(deleted) => { setPosterKey(k => k + 1); if (deleted) { setPosterDeleted(true); if (!isAggregate) setScrapeData(null); } else { setPosterDeleted(false); } if (!isAggregate) reload(); refreshFolderTree(); }} />
          </div>
          <FeatureTip tipKey="poster_upload" message="💡 点击右上角按钮可更换封面" />
        </div>
      )}
      {/* 媒体文件夹：分类标签选择器（仅 is_virtual_library） */}
      {node.is_virtual_library && (
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500">分类标签</span>
          <select value={node.category_tag || "movie"} onChange={async (e) => {
            const newTag = e.target.value;
            try {
              await fetch(`${BASE_URL}/library/category-tag`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({path: node.path, tag: newTag})
              });
              await refreshFolderTree();
            } catch {}
          }} className="text-[11px] px-2 py-0.5 rounded-md font-medium bg-[#1a1a1a] text-slate-400 border border-white/[0.08] outline-none cursor-pointer">
            {[
              {v: "movie", l: "电影"},
              {v: "tv", l: "剧集"},
              {v: "anime_tv", l: "动画番剧"},
              {v: "anime_movie", l: "动画电影"},
              {v: "variety", l: "综艺"},
              {v: "other", l: "其他"},
            ].map(t => (
              <option key={t.v} value={t.v}>{t.l}</option>
            ))}
          </select>
        </div>
      )}
      {/* 文件夹类型标签（内容文件夹，非媒体文件夹） */}
      {folderType && !node.is_virtual_library && (
        <div className="flex items-center gap-2">
          <select value={folderType} onChange={async (e) => {
            const newType = e.target.value;
            try {
              await fetch(`${BASE_URL}/library/folder-type`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({path: node.path, folder_type: newType})
              });
              await refreshFolderTree();
            } catch {}
          }} className="text-[11px] px-2 py-0.5 rounded-md font-medium bg-[#1a1a1a] text-slate-400 border border-white/[0.08] outline-none cursor-pointer">
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
      {/* 识别信息：只在末端识别单元（movie/tv/season）时显示 */}
      {!isAggregate && scrapeLoading && <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-blue-500/10 border border-blue-500/20"><div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin flex-shrink-0" /><span className="text-xs text-blue-400">正在识别...</span></div>}
      {!isAggregate && scrapeStatus === "success" && !scrapeLoading && scrape && (scrape.tmdb_id > 0 || scrape.title) && <><div className="text-xs text-green-400/70">✓ {scrape.title || "已匹配"}</div><ScrapeInfo data={scrape} /></>}
      {!isAggregate && confidence && <ConfidenceBadge confidence={confidence} pendingConfirm={pendingConfirm} onConfirm={() => setPendingConfirm(false)} onReject={() => { setPendingConfirm(false); }} />}
      {/* movie 类型显示视频级标准名，tv/season 显示文件夹级标准名 */}
      {folderType === "movie" && node.videos[0] && (
        <ShadowNameSection path={node.videos[0].file_path} video={node.videos[0]} cleanNameEn={node.clean_name_en || node.videos[0]?.clean_name_en} onRefresh={onRefresh} />
      )}
      {(folderType === "tv" || folderType === "season") && (
        <ShadowNameSection path={node.path} folderName={node.name} folderShadowName={node.shadow_name} folderCleanName={node.clean_name} cleanNameEn={node.clean_name_en} onRefresh={onRefresh} onTreeRefresh={onTreeRefresh} />
      )}
      {/* 季集完整度 */}
      {(folderType === "tv" || folderType === "season") && (
        <CompletenessBar
          path={folderType === "season" ? (node.path.substring(0, node.path.lastIndexOf('\\')) || node.path.substring(0, node.path.lastIndexOf('/'))) : node.path}
          folderType="tv"
          tmdbId={scrape?.tmdb_id || undefined}
          onSearch={onSearch}
          cnName={node.clean_name_cn || node.clean_name || ""}
          enName={node.clean_name_en || ""}
          seasonFilter={folderType === "season" ? (() => {
            const CN_NUM: Record<string, number> = { "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10 };
            const sMatch = node.name.match(/(?:Season|S)\s*(\d+)/i) || node.name.match(/第(\d+)季/);
            if (sMatch) return parseInt(sMatch[1]);
            const cnMatch = node.name.match(/第([一二三四五六七八九十]+)季/);
            if (cnMatch) {
              const s = cnMatch[1];
              if (s.length === 1) return CN_NUM[s];
              if (s === "十") return 10;
              if (s.startsWith("十")) return 10 + (CN_NUM[s[1]] || 0);
              if (s.endsWith("十")) return (CN_NUM[s[0]] || 0) * 10;
            }
            return undefined;
          })() : undefined}
        />
      )}
      <div className="grid grid-cols-3 gap-2">
        {[[String(node.video_count), "视频"], [String(node.children?.length || 0), "子目录"], [formatSize(totalSize), "总大小"]].map(([v, l]) => (
          <div key={l} className="bg-white/[0.04] rounded-lg p-2.5 text-center"><p className="text-base font-semibold text-white">{v}</p><p className="text-[11px] text-slate-500">{l}</p></div>
        ))}
      </div>
      {/* 第一行操作按钮 */}
      {(() => {
        // 直接用结构化的清洗名字段，旧数据回退时从 clean_name 拆分
        let cnName = node.clean_name_cn || "";
        let enName = node.clean_name_en || "";
        const originalName = node.clean_name_original || "";
        // 旧数据没有结构化字段时，从 clean_name/name 中拆分中英文
        if (!cnName && !enName) {
          const raw = node.clean_name || node.name || "";
          const cnMatch = raw.match(/[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+/g);
          const enMatch = raw.match(/[a-zA-Z][a-zA-Z0-9\s'.:-]*/g);
          cnName = cnMatch ? cnMatch.join("").trim() : raw;
          enName = enMatch ? enMatch.map(s => s.trim()).filter(Boolean).join(" ") : "";
          if (cnName === enName) enName = "";
        }
        if (!cnName) {
          // 过滤一级分类目录名，避免搜索词变成"电影白"
          const raw = node.clean_name || node.name;
          const categoryNames = ["电影", "动画电影", "电视剧", "动画番", "其他视频", "综艺", "纪录片"];
          cnName = categoryNames.includes(raw) ? "" : raw;
        }
        const ft = node.folder_type || "";
        // 季号：从 node.name 中提取（支持阿拉伯数字和中文数字）
        const CN_NUM: Record<string, number> = { "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10 };
        const sMatch = node.name.match(/(?:Season|S)\s*(\d+)/i) || node.name.match(/第(\d+)季/);
        let sNum: number | undefined;
        if (sMatch) {
          sNum = parseInt(sMatch[1]);
        } else {
          const cnMatch = node.name.match(/第([一二三四五六七八九十]+)季/);
          if (cnMatch) {
            const cnStr = cnMatch[1];
            if (cnStr.length === 1) sNum = CN_NUM[cnStr];
            else if (cnStr === "十") sNum = 10;
            else if (cnStr.startsWith("十")) sNum = 10 + (CN_NUM[cnStr[1]] || 0);
            else if (cnStr.endsWith("十")) sNum = (CN_NUM[cnStr[0]] || 0) * 10;
            else if (cnStr.includes("十")) {
              // "二十一" → 21
              const parts = cnStr.split("十");
              sNum = (CN_NUM[parts[0]] || 0) * 10 + (CN_NUM[parts[1]] || 0);
            } else sNum = undefined;
          }
        }
        // 默认搜索词
        const defaultQuery = ft === "season" && sNum
          ? `${cnName} Season ${sNum}`
          : (cnName && enName && cnName !== enName ? `${cnName} ${enName}` : cnName);
        const ctx = { cnName, enName, originalName, folderType: ft, seasonNumber: sNum, savePath: node.path };
        return isAggregate ? (
          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => onSearch(defaultQuery, ctx)} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-300">搜索升级</button>
            <button onClick={rescrape} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-300">自动刮削</button>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            <button onClick={() => onSearch(defaultQuery, ctx)} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-300">搜索升级</button>
            <button onClick={rescrape} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-300">自动刮削</button>
            <CandidatePicker name={node.clean_name || node.videos[0]?.clean_name || node.name} path={node.path} onSelected={(d) => { if (d) setScrapeData(d); setPosterKey(k => k + 1); refreshFolderTree(); }} />
          </div>
        );
      })()}
      {/* 第二行：移动到 / 复制到 / 删除 / 移除 */}
      {node.is_virtual_library ? (
        <div className="grid grid-cols-2 gap-2">
          <button onClick={async () => {
            if (!confirm(`确定从媒体库中移除 "${node.name}"？（不会删除文件）`)) return;
            try {
              await api.deleteLibrary(node.name);
              onRefresh();
            } catch { alert("移除失败"); }
          }} className="py-2 rounded-lg bg-white/[0.04] hover:bg-red-500/10 hover:text-red-400 text-xs text-slate-500 transition-all">移除文件夹</button>
          <button onClick={() => {
            const newName = prompt("修改文件夹名称", node.name);
            if (newName && newName !== node.name) {
              api.updateLibrary(node.name, { name: newName }).then(() => onRefresh()).catch(() => alert("修改失败"));
            }
          }} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.06] text-xs text-slate-500">改名</button>
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-2">
          <MoveAction onMove={handleMove} />
          <CopyAction onCopy={async (t) => { try { await api.batchManage("copy", [node.path], t); onRefresh(); } catch { alert("失败"); } }} />
          <DeleteAction onDelete={handleDelete} />
          <button onClick={handleRemove} className="py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.06] text-xs text-slate-500">移除</button>
        </div>
      )}
      {/* 第三行：名字类操作 / 自动重命名 / 标准结构 / 一键整理（虚拟文件夹不显示） */}
      {!node.is_virtual_library && (
      <div className="space-y-2">
        {/* 生成检索名 + 生成标准名：只对"一部作品"有意义，
            所以只给 movie 和 tv；season、单集、以及合集/系列这类聚合节点不给 */}
        {(folderType === "movie" || folderType === "tv") && (
          <div className="grid grid-cols-2 gap-2">
            <ActionButton label="生成检索名" emphasis busy={generatingIndex} onClick={handleGenerateIndexName}
              title="按 NFO / 文件夹名 / 文件名生成中英文检索名，搜索字幕和资源会更准" />
            <ActionButton label="生成标准名" busy={shadowNameLoading} onClick={handleGenerateShadowName}
              title="只写入标准名，不改磁盘上的文件名" />
          </div>
        )}
        <button onClick={() => doAction("rename_shadow")} disabled={actionLoading} className="w-full py-2.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-sm text-slate-300 disabled:opacity-50">自动重命名</button>
        <button onClick={handleStructurePreview} disabled={actionLoading} className="w-full py-2.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-sm text-slate-300 disabled:opacity-50">标准结构</button>
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
      )}
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
          {actionResult.startsWith("预览-organize") && (
            <button onClick={() => doAction("organize", false)} disabled={actionLoading}
              className="mt-2 w-full py-2 rounded-lg bg-blue-600/80 hover:bg-blue-500 text-sm font-medium disabled:opacity-50">确认执行</button>
          )}
          {actionResult.startsWith("预览-structure") && (
            <button onClick={async () => { setActionLoading(true); try { const res = await api.structureOrganize(node.path, false); setActionResult("结构整理完成: " + (res.count || 0) + " 项操作"); onRefresh(); } catch (e: any) { setActionResult("执行失败: " + (e?.message || String(e))); } setActionLoading(false); }} disabled={actionLoading}
              className="mt-2 w-full py-2 rounded-lg bg-blue-600/80 hover:bg-blue-500 text-sm font-medium disabled:opacity-50">确认执行</button>
          )}
          {actionResult.startsWith("预览") && !actionResult.includes("预览-organize") && !actionResult.includes("预览-structure") && (
            <button onClick={() => doAction(lastAction, false)} disabled={actionLoading}
              className="mt-2 w-full py-2 rounded-lg bg-blue-600/80 hover:bg-blue-500 text-sm font-medium disabled:opacity-50">确认执行</button>
          )}
        </div>
      )}
      <InfoRow label="大小" value={formatSize(totalSize)} />
      <InfoRow label="路径" value={node.path} />
      {!isRoot && !isAggregate && (
        <button onClick={toggleNoScrape} className={`w-full py-2 rounded-lg text-xs transition-all ${noScrape ? "bg-red-500/20 text-red-400 border border-red-500/30" : "bg-white/[0.04] text-slate-500 hover:bg-white/[0.06]"}`}>
          {noScrape ? "🚫 已禁止识别（点击解除）" : "禁止识别此文件夹"}
        </button>
      )}
    </div>
  );
}

// ── 视频详情 ──
