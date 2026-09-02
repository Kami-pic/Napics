// 视频详情面板：展示视频信息、刮削状态、操作按钮
"use client";
import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import type { VideoInfo } from "@/types";
import { api } from "@/lib/api";
import { formatSize, formatDuration } from "@/lib/utils";
import { getCached, setCached } from "./detailCache";
import { useScrape } from "./useScrape";
import { Poster, InfoRow, MoveAction, CopyAction, DeleteAction, ConfidenceBadge, ScrapeInfo, ActionButton } from "./DetailComponents";
import { CandidatePicker } from "./CandidatePicker";
import { ShadowNameSection } from "./ShadowNameSection";
import { PosterUpload } from "./PosterUpload";
import { PlayButton } from "./PlayButton";
import QualityProbeButton from "./QualityProbeButton";
import { useInstalledPlugins } from "@/hooks/useInstalledPlugins";

// 字幕弹窗动态加载 — 仅在插件安装后实际加载代码
const SubtitleModal = dynamic(() => import("@/components/subtitle/SubtitleModal"), { ssr: false });

export function VideoDetail({ video: v, onPlay, onSearch, onRefresh }: { video: VideoInfo; onPlay: (p: string) => void; onSearch: (q: string, ctx?: any) => void; onRefresh: () => void }) {
  const { data: scrape, loading: scrapeLoading, status: scrapeStatus, rescrape: _rescrape, reload, setData: setScrapeData, confidence, pendingConfirm, setPendingConfirm } = useScrape(v.clean_name || v.file_name, v.file_path, false);
  const rescrape = async () => { await _rescrape(); setPosterKey(k => k + 1); setPosterDeleted(false); onRefresh(); };
  const [posterKey, setPosterKey] = useState(0);
  const [posterDeleted, setPosterDeleted] = useState(false);
  const [showSubtitle, setShowSubtitle] = useState(false);
  const plugins = useInstalledPlugins();
  const hasSubtitle = plugins.installed.has("subtitle-search");
  // 外挂字幕（ffprobe 的 subtitle_count 只统计内封轨，看不到同目录的 .srt/.ass）
  const [externalSubs, setExternalSubs] = useState<string[]>([]);
  const loadExternalSubs = () => {
    api.getMediaSubtitles(v.file_path)
      .then(res => setExternalSubs(res.files || []))
      .catch(() => setExternalSubs([]));
  };
  useEffect(() => { loadExternalSubs(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [v.file_path]);
  const handleMove = async (t: string) => { try { await api.batchManage("move", [v.file_path], t); onRefresh(); } catch { alert("失败"); } };
  const handleDelete = async () => { try { await api.batchManage("delete", [v.file_path]); onRefresh(); } catch { alert("失败"); } };
  const [renameResult, setRenameResult] = useState(() => getCached(v.file_path).renameResult || "");
  const [renameLoading, setRenameLoading] = useState(false);
  const [structureLoading, setStructureLoading] = useState(false);
  const [generatingIndex, setGeneratingIndex] = useState(false);
  const [structureResult, setStructureResult] = useState(() => getCached(v.file_path).structureResult || "");

  // 同步到缓存
  useEffect(() => {
    setCached(v.file_path, { renameResult, structureResult });
  }, [v.file_path, renameResult, structureResult]);

  // 判断是否已封装：视频所在文件夹只有这一个视频（或少量关联文件）→ 已封装
  // 简单判断：视频的父目录名不是一级分类目录常见名 → 已封装
  // 单集判定：文件名带 SxxExx 的按剧集处理，名字类操作交给所属剧集文件夹
  const isEpisode = /S\d+E\d+/i.test(v.file_name);
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
  // 生成检索名：按 NFO → 文件夹名 → 文件名 重算中英文索引名
  const handleGenerateIndexName = async () => {
    setGeneratingIndex(true);
    try {
      const res = await api.generateCleanName(v.file_path);
      if (res.status !== "ok") { alert(`生成检索名失败\n\n${res.message || "未能解析出名称，请手动填写"}`); return; }
      onRefresh();
    } catch (e: any) { alert(`生成检索名失败\n\n${e?.message || e}`); }
    setGeneratingIndex(false);
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
      {/* 封面传视频自身路径，不传所在目录：目录模式下后端会取 listdir 到的第一个
          `*-poster.jpg`，散装电影（一个目录塞几十部片）会全部显示成同一张 */}
      <div className="relative"><Poster key={posterKey} fallbackName={v.file_name} localPath={v.file_path} aspect="poster" posterDeleted={posterDeleted} /><div className="absolute top-2 right-2 z-10"><PosterUpload path={v.file_path} onUploaded={(deleted) => { setPosterKey(k => k + 1); if (deleted) { setPosterDeleted(true); setScrapeData(null); } else { setPosterDeleted(false); } reload(); onRefresh(); }} /></div></div>
      {scrapeLoading && <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-blue-500/10 border border-blue-500/20"><div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin flex-shrink-0" /><span className="text-xs text-blue-400">正在刮削...</span></div>}
      {scrapeStatus === "success" && !scrapeLoading && scrape && <><div className="text-xs text-green-400/70">✓ {scrape.title || "已匹配"}</div><ScrapeInfo data={scrape} /></>}
      {confidence && <ConfidenceBadge confidence={confidence} pendingConfirm={pendingConfirm} onConfirm={() => setPendingConfirm(false)} onReject={() => { setPendingConfirm(false); }} />}
      <ShadowNameSection path={v.file_path} video={v} onRefresh={onRefresh} />
      {/* 第一行：搜索升级 / 一键刮削 / 重新匹配 */}
      {(() => {
        // 直接用结构化的清洗名字段，旧数据回退时从 clean_name 拆分
        let cnName = v.clean_name_cn || "";
        let enName = v.clean_name_en || "";
        const originalName = v.clean_name_original || "";
        if (!cnName && !enName) {
          const raw = v.clean_name || v.folder_name || v.file_name || "";
          const cnMatch = raw.match(/[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+/g);
          const enMatch = raw.match(/[a-zA-Z][a-zA-Z0-9\s'.:-]*/g);
          cnName = cnMatch ? cnMatch.join("").trim() : raw;
          enName = enMatch ? enMatch.map(s => s.trim()).filter(Boolean).join(" ") : "";
          if (cnName === enName) enName = "";
        }
        if (!cnName) {
          // 过滤一级分类目录名，避免搜索词变成"电影白"
          const raw = v.clean_name || v.folder_name || v.file_name;
          const categoryNames = ["电影", "动画电影", "电视剧", "动画番", "其他视频", "综艺", "纪录片"];
          cnName = categoryNames.includes(raw) ? "" : raw;
        }
        // 从文件名提取季集号
        const seMatch = v.file_name.match(/S(\d+)E(\d+)/i);
        const sNum = seMatch ? parseInt(seMatch[1]) : undefined;
        const eNum = seMatch ? parseInt(seMatch[2]) : undefined;
        const epTag = sNum !== undefined && eNum !== undefined ? `S${String(sNum).padStart(2,"0")}E${String(eNum).padStart(2,"0")}` : undefined;
        // 默认搜索词：集文件用 中文名+SxxExx
        const defaultQuery = epTag ? `${cnName} ${epTag}` : (cnName && enName && cnName !== enName ? `${cnName} ${enName}` : cnName);
        const ctx = { cnName, enName, originalName, folderType: "", seasonNumber: sNum, episodeTag: epTag, savePath: v.file_path.replace(/[\\/][^\\/]+$/, '') };
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
      {/* 第三行：生成检索名 / 生成标准名（两者都是"整部作品"级别的名字，单集不给，
          单集统一在所属剧集文件夹上处理，避免每集各生成一份不一致的名字）*/}
      {!isEpisode && (
        <div className="grid grid-cols-2 gap-2">
          <ActionButton label="生成检索名" emphasis busy={generatingIndex} onClick={handleGenerateIndexName}
            title="按 NFO / 文件夹名 / 文件名生成中英文检索名，搜索字幕和资源会更准" />
          <ActionButton label="生成标准名" busy={renameLoading} onClick={() => handleAutoRename(false, true)}
            title="只写入标准名，不改磁盘上的文件名" />
        </div>
      )}
      {/* 第四行：播放 / 标准结构（各自独占一行）*/}
      <div className="space-y-2">
        <PlayButton filePath={v.file_path} onPlay={onPlay} />
        <button onClick={handleStructure} disabled={structureLoading || !isLooseVideo} className={`w-full py-2.5 rounded-lg text-sm disabled:opacity-50 ${isLooseVideo ? "bg-white/[0.04] hover:bg-white/[0.08] text-slate-300" : "bg-white/[0.02] text-slate-600 cursor-not-allowed"}`}>{structureLoading ? "处理中..." : isLooseVideo ? "标准结构" : "✓ 已封装"}</button>
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
        <div className="flex items-center justify-between mb-2">
          <h5 className="text-sm font-medium text-slate-300">文件信息</h5>
          <div className="flex items-center gap-2">
            {hasSubtitle && (
              <button
                onClick={() => setShowSubtitle(true)}
                className="text-[11px] text-slate-500 hover:text-green-400 transition-colors"
                title="搜索字幕"
              >搜索字幕</button>
            )}
            <QualityProbeButton filePath={v.file_path} onDone={onRefresh} />
          </div>
        </div>
        {(() => {
          // 字幕状态：内封轨按可用性拆分（文本可直接显示，图形需 OCR）+ 外挂文件。
          // 混合片源很常见（同片 subrip 和 PGS 各一套），分开列出并用逗号隔开。
          const total = v.subtitle_count || 0;
          const graphic = v.subtitle_graphic_count ?? 0;
          // 存量记录没有拆分字段，退化为"内封 N 条"不区分类型
          const text = v.subtitle_text_count ?? (graphic ? total - graphic : total);
          const external = externalSubs.length;
          const parts: string[] = [];
          if (text > 0) parts.push(`内封 ${text} 条`);
          if (graphic > 0) parts.push(`图形 ${graphic} 条`);
          if (external > 0) parts.push(`外挂 ${external} 个`);
          const subtitleValue = parts.length ? parts.join(", ") : "无";
          // 容器格式：优先用扫描到的 container，存量记录退化用扩展名
          const container = (v.container || v.file_name.split(".").pop() || "").toUpperCase();
          const rows: [string, string, boolean, boolean][] = [
            ["分辨率", v.resolution, false, false],
            ["视频格式", container || "—", false, false],
            ["视频编码", v.codec || v.video_codec || "—", false, false],
            ["音频编码", v.audio_codec || "—", false, false],
            ["HDR", v.hdr_type, false, false],
            ["质量分", String(v.quality_score || 0), false, false],
            ["时长", formatDuration(v.duration_min ?? v.duration), false, false],
            // 无字幕、或只有图形字幕（播放器渲染不了）都标橙；有可用字幕标绿
            ["字幕", subtitleValue,
              parts.length === 0 || (text === 0 && external === 0 && graphic > 0),
              external > 0 || text > 0],
            ["画质", v.is_low_res ? "低画质" : "正常", v.is_low_res, false],
            // 大小紧贴路径上面 —— 和文件夹详情那边保持同一个顺序
            ["大小", formatSize(v.size_gb), false, false],
            ["路径", v.file_path, false, false],
          ];
          return rows.map(([label, value, warn, ok]) => (
            <InfoRow key={label} label={label} value={value} warn={warn} ok={ok} />
          ));
        })()}
      </div>
      {/* 字幕搜索弹窗（插件已安装时才渲染） */}
      {hasSubtitle && (() => {
        // 与「搜索升级」用同一套名称与季集信息，保证搜索词一致
        const seMatch = v.file_name.match(/S(\d+)E(\d+)/i);
        const sNum = seMatch ? parseInt(seMatch[1]) : undefined;
        const eNum = seMatch ? parseInt(seMatch[2]) : undefined;
        const epTag = sNum !== undefined && eNum !== undefined
          ? `S${String(sNum).padStart(2, "0")}E${String(eNum).padStart(2, "0")}`
          : undefined;
        return (
          <SubtitleModal
            open={showSubtitle}
            onClose={() => setShowSubtitle(false)}
            videoPath={v.file_path}
            query={v.clean_name_cn || v.clean_name || v.file_name.replace(/\.[^.]+$/, "")}
            cnName={v.clean_name_cn || ""}
            enName={v.clean_name_en || ""}
            originalName={v.clean_name_original || ""}
            seasonNumber={sNum}
            episodeNumber={eNum}
            episodeTag={epTag}
            onDownloaded={loadExternalSubs}
          />
        );
      })()}
    </div>
  );
}

// ── 通用组件 ──
