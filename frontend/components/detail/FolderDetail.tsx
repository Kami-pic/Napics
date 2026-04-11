// 文件夹详情面板：展示文件夹信息、刮削状态、操作按钮
"use client";
import { useState, useEffect, useMemo } from "react";
import type { FolderNode } from "@/types";
import { api } from "@/lib/api";
import { formatSize } from "@/lib/utils";
import { FOLDER_TYPE_LABELS, isAggregate as isAggregateType } from "@/lib/folderTypes";
import { getCached, setCached } from "./detailCache";
import { useScrape } from "./useScrape";
import { Poster, InfoRow, MoveAction, CopyAction, DeleteAction, ConfidenceBadge, ScrapeInfo } from "./DetailComponents";
import { CandidatePicker } from "./CandidatePicker";
import { ShadowNameSection } from "./ShadowNameSection";
import { PosterUpload } from "./PosterUpload";

export function FolderDetail({ node, onRefresh, onSearch, currentCategoryTag }: { node: FolderNode; onRefresh: () => void; onSearch: (q: string, ctx?: any) => void; currentCategoryTag: string }) {
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
        const res = await api.renameVideos(node.path, false, true);
        setActionResult(`已更新标准名：${res.filled || res.shadow_filled || 0} 项`);
        setTimeout(() => onRefresh(), 300);
      } else if (action === "rename_real") {
        const res = await api.renameVideos(node.path, false, false);
        setLastSnapshotId(res.snapshot_id || null);
        setActionResult("替换原始名完成");
        setTimeout(() => onRefresh(), 300);
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
          if (archivePlan.length) msg += `\n🗑️ 旧刮削清理: ${archivePlan.length} 个目录`;
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
            if (steps.archive) msg += `\n旧刮削清理: ${steps.archive} 项`;
            if (steps.scrape?.nfo_written) msg += `\n刮削: ${steps.scrape.nfo_written} 个 NFO`;
            if (steps.structure?.moved) msg += `\n结构归位: ${steps.structure.moved} 项`;
            if (steps.shadow) msg += `\n影子名: ${steps.shadow} 项`;
            setActionResult(msg);
            setActionPlan(null);
            onRefresh();
          } else {
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
