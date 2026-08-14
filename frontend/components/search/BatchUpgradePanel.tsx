// 批量搜索升级面板（全屏弹窗）
"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import type { BatchUpgradeTask, EnhancedSearchResult } from "@/types";
import { api } from "@/lib/api";

// ── 阶段类型 ──
type Phase = "searching" | "review" | "downloading" | "done";

interface BatchUpgradePanelProps {
  open: boolean;
  onClose: () => void;
  items: { name: string; path: string; currentResolution: string }[];
  qbConfigured: boolean;
  alistConfigured: boolean;
}

export default function BatchUpgradePanel({
  open, onClose, items, qbConfigured, alistConfigured,
}: BatchUpgradePanelProps) {
  const [phase, setPhase] = useState<Phase>("searching");
  const [tasks, setTasks] = useState<BatchUpgradeTask[]>([]);
  const [progress, setProgress] = useState({ current: 0, total: 0, currentName: "" });
  const [downloadResult, setDownloadResult] = useState({ success: 0, failed: 0 });
  const [downloadChannel, setDownloadChannel] = useState<"qb" | "alist">(
    qbConfigured ? "qb" : "alist"
  );
  const abortRef = useRef<AbortController | null>(null);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  // 后端明确报出的失败原因（如未安装搜索插件），必须展示而不是静默出现空列表
  const [searchError, setSearchError] = useState("");

  const toggleExpand = (index: number) => {
    setExpandedIndex(expandedIndex === index ? null : index);
  };

  // 打开时启动批量搜索
  useEffect(() => {
    if (open && items.length > 0) {
      startBatchSearch();
    }
    if (!open) {
      // 重置状态
      abortRef.current?.abort();
      setPhase("searching");
      setTasks([]);
      setProgress({ current: 0, total: 0, currentName: "" });
      setDownloadResult({ success: 0, failed: 0 });
      setSearchError("");
    }
  }, [open]);

  // ── 批量搜索（EventSource 流式） ──
  const startBatchSearch = useCallback(async () => {
    setPhase("searching");
    const initTasks: BatchUpgradeTask[] = items.map((it) => ({
      name: it.name,
      path: it.path,
      currentResolution: it.currentResolution,
      status: "pending",
      bestMatch: null,
      allResults: [],
      confirmed: false,
      matchScore: 0,
      confidence: "",
      isUpgrade: false,
    }));
    setTasks(initTasks);
    setProgress({ current: 0, total: items.length, currentName: "" });

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const resp = await api.batchSearch(
        items.map((it) => ({
          name: it.name,
          path: it.path,
          current_resolution: it.currentResolution,
        }))
      );

      if (!resp.ok || !resp.body) {
        // 请求失败，全部标记 error
        setTasks((prev) =>
          prev.map((t) => ({ ...t, status: "error" as const }))
        );
        setSearchError(`搜索请求失败（${resp.status}），请检查后端是否正常运行`);
        setPhase("review");
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        if (ctrl.signal.aborted) break;
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;
          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr) continue;

          try {
            const evt = JSON.parse(jsonStr);
            handleSSEEvent(evt);
          } catch {
            // 忽略解析错误
          }
        }
      }
    } catch {
      // 连接中断：用户主动取消时不提示，其余情况给出原因
      if (!ctrl.signal.aborted) {
        setSearchError("搜索连接中断，请检查网络或稍后重试");
      }
    }

    // 搜索完成，进入 review 阶段
    setPhase("review");
  }, [items]);

  // ── 处理 SSE 事件 ──
  const handleSSEEvent = useCallback((evt: any) => {
    if (evt.type === "progress") {
      setProgress({
        current: evt.index + 1,
        total: evt.total,
        currentName: evt.name || "",
      });
      setTasks((prev) =>
        prev.map((t, i) =>
          i === evt.index ? { ...t, status: "searching" } : t
        )
      );
    } else if (evt.type === "result") {
      const bestMatch: EnhancedSearchResult | null = evt.best_match
        ? {
            ...evt.best_match,
            quality: evt.best_match.quality || {
              resolution: "", source: "", video_codec: "",
              audio_codec: "", has_chinese_sub: false, release_group: "",
              display: evt.best_match.quality_tag || "",
            },
            quality_rank: evt.best_match.quality_rank ?? 0,
          }
        : null;

      const allResults: EnhancedSearchResult[] = (evt.all_results || []).map(
        (r: any) => ({
          ...r,
          quality: r.quality || {
            resolution: "", source: "", video_codec: "",
            audio_codec: "", has_chinese_sub: false, release_group: "",
            display: r.quality_tag || "",
          },
          quality_rank: r.quality_rank ?? 0,
        })
      );

      const status = bestMatch ? "found" : "not_found";
      const matchScore = evt.match_score ?? 0;
      const confidence = evt.confidence ?? "";
      const isUpgrade = evt.is_upgrade ?? false;
      // 自动确认：score >= 0.5 且有提升
      const autoConfirm = !!bestMatch && matchScore >= 0.5 && isUpgrade;
      setTasks((prev) =>
        prev.map((t, i) =>
          i === evt.index
            ? { ...t, status, bestMatch, allResults, confirmed: autoConfirm, matchScore, confidence, isUpgrade }
            : t
        )
      );
      setProgress((p) => ({ ...p, current: evt.index + 1 }));
    } else if (evt.type === "error") {
      setTasks((prev) =>
        prev.map((t, i) =>
          i === evt.index ? { ...t, status: "error" } : t
        )
      );
    } else if (evt.type === "done") {
      if (evt.error) {
        setSearchError(evt.message || "没有可用的搜索源");
      }
      setProgress((p) => ({ ...p, current: p.total }));
    }
  }, []);

  // ── 确认/移除操作 ──
  const toggleConfirm = (index: number) => {
    setTasks((prev) =>
      prev.map((t, i) =>
        i === index ? { ...t, confirmed: !t.confirmed } : t
      )
    );
  };

  const removeTask = (index: number) => {
    setTasks((prev) =>
      prev.map((t, i) =>
        i === index ? { ...t, confirmed: false, bestMatch: null, status: "not_found" as const } : t
      )
    );
  };

  const confirmAll = () => {
    setTasks((prev) =>
      prev.map((t) =>
        t.status === "found" && t.bestMatch && t.matchScore >= 0.5 && t.isUpgrade
          ? { ...t, confirmed: true }
          : t
      )
    );
  };

  // ── 批量下载 ──
  const handleDownloadAll = async () => {
    const confirmed = tasks.filter((t) => t.confirmed && t.bestMatch);
    if (confirmed.length === 0) return;

    setPhase("downloading");
    setDownloadResult({ success: 0, failed: 0 });

    try {
      const downloadTasks = confirmed.map((t) => ({
        download_url: t.bestMatch!.download_url,
        save_path: t.path,
        download_type: downloadChannel,
      }));

      const resp = await api.batchDownload(downloadTasks);
      const results: { success: boolean }[] = resp.results || [];
      const success = results.filter((r) => r.success).length;
      const failed = results.length - success;
      setDownloadResult({ success, failed });
    } catch {
      setDownloadResult({ success: 0, failed: confirmed.length });
    }

    setPhase("done");
  };

  // ── 统计 ──
  const foundCount = tasks.filter((t) => t.status === "found").length;
  const notFoundCount = tasks.filter((t) => t.status === "not_found").length;
  const errorCount = tasks.filter((t) => t.status === "error").length;
  const confirmedCount = tasks.filter((t) => t.confirmed && t.bestMatch).length;
  const progressPct = progress.total > 0 ? (progress.current / progress.total) * 100 : 0;

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/90 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* 顶栏 */}
        <div className="p-5 border-b border-slate-700">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold">批量搜索升级</h2>
              <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-300">
                {tasks.length} 个视频
              </span>
            </div>
            <button
              onClick={() => { abortRef.current?.abort(); onClose(); }}
              className="text-slate-400 hover:text-white text-xl"
            >
              ✕
            </button>
          </div>
        </div>

        {/* 内容区 */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* ── 搜索阶段 ── */}
          {phase === "searching" && (
            <div className="space-y-6">
              <div className="flex flex-col items-center py-8">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mb-4" />
                <p className="text-sm text-slate-300 mb-1">
                  正在搜索 ({progress.current}/{progress.total})
                </p>
                {progress.currentName && (
                  <p className="text-xs text-slate-500 truncate max-w-md">
                    {progress.currentName}
                  </p>
                )}
                {/* 进度条 */}
                <div className="w-full max-w-md mt-4 bg-slate-700 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-blue-500 h-full rounded-full transition-all duration-300"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
              </div>

              {/* 实时任务列表 */}
              <div className="space-y-2">
                {tasks.map((t, i) => (
                  <div
                    key={i}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
                      t.status === "searching"
                        ? "bg-blue-500/10 border border-blue-500/30"
                        : t.status === "found"
                        ? "bg-green-500/10 border border-green-500/20"
                        : t.status === "not_found" || t.status === "error"
                        ? "bg-slate-900 border border-slate-700 opacity-60"
                        : "bg-slate-900 border border-slate-700/50"
                    }`}
                  >
                    <StatusIcon status={t.status} />
                    <span className="flex-1 truncate text-slate-300">{t.name}</span>
                    <span className="text-xs text-slate-500">{t.currentResolution}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── 结果汇总阶段 ── */}
          {phase === "review" && (
            <div className="space-y-4">
              {/* 失败原因（如未安装搜索插件），避免只显示"未找到"让人无从下手 */}
              {searchError && (
                <div className="px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-300">
                  {searchError}
                </div>
              )}

              {/* 汇总统计 */}
              <div className="flex items-center gap-4 text-sm">
                <span className="text-green-400">✓ 找到 {foundCount}</span>
                <span className="text-slate-500">✗ 未找到 {notFoundCount}</span>
                {errorCount > 0 && (
                  <span className="text-red-400">⚠ 错误 {errorCount}</span>
                )}
                <div className="flex-1" />
                <button
                  onClick={confirmAll}
                  className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-medium transition-colors"
                >
                  全部确认
                </button>
              </div>

              {/* 结果表格 */}
              <div className="space-y-2">
                {tasks.map((t, i) => (
                  <div
                    key={i}
                    className={`bg-slate-900 rounded-xl border p-4 ${
                      t.confirmed
                        ? "border-blue-500/40"
                        : "border-slate-700"
                    }`}
                  >
                    <div className="flex items-center gap-4">
                      {/* 视频名称 */}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-200 truncate">
                          {t.name}
                        </p>
                        <p className="text-xs text-slate-500 mt-0.5">
                          当前：{t.currentResolution || "未知"}
                        </p>
                      </div>

                      {/* 推荐资源信息 */}
                      {t.status === "found" && t.bestMatch ? (
                        <div className="flex items-center gap-4 flex-shrink-0">
                          {/* 置信度徽章 */}
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                            t.confidence === "high" ? "bg-green-500/15 text-green-400" :
                            t.confidence === "medium" ? "bg-yellow-500/15 text-yellow-400" :
                            "bg-red-500/15 text-red-400"
                          }`}>
                            {(t.matchScore * 100).toFixed(0)}分
                          </span>
                          {!t.isUpgrade && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">无提升</span>
                          )}
                          <span className="text-xs font-bold text-green-400">
                            {t.bestMatch.quality?.display || t.bestMatch.quality_tag}
                          </span>
                          <span className="text-xs text-slate-400">
                            {t.bestMatch.size_gb} GB
                          </span>
                          <span className="text-xs text-green-500">
                            做种: {t.bestMatch.seeders}
                          </span>
                          {/* 确认/查看备选/移除按钮 */}
                          <div className="flex gap-1">
                            <button
                              onClick={() => toggleConfirm(i)}
                              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                                t.confirmed
                                  ? "bg-blue-600 text-white"
                                  : "bg-slate-700 text-slate-400 hover:bg-slate-600"
                              }`}
                            >
                              {t.confirmed ? "已确认" : "确认"}
                            </button>
                            <button
                              onClick={() => toggleExpand(i)}
                              className="px-2.5 py-1 rounded text-xs text-slate-500 hover:text-blue-400 hover:bg-blue-500/10 transition-colors"
                            >
                              备选
                            </button>
                            <button
                              onClick={() => removeTask(i)}
                              className="px-2.5 py-1 rounded text-xs text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                            >
                              移除
                            </button>
                          </div>
                        </div>
                      ) : (
                        <span className={`text-xs ${
                          t.status === "error" ? "text-red-400" : "text-slate-500"
                        }`}>
                          {t.status === "error" ? "搜索出错" : "未找到资源"}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── 下载中阶段 ── */}
          {phase === "downloading" && (
            <div className="flex flex-col items-center py-16">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mb-4" />
              <p className="text-sm text-slate-300">
                正在推送下载任务 ({confirmedCount} 个)...
              </p>
              <p className="text-xs text-slate-500 mt-1">
                通道：{downloadChannel === "qb" ? "qBittorrent" : "OpenList"}
              </p>
            </div>
          )}

          {/* ── 完成阶段 ── */}
          {phase === "done" && (
            <div className="flex flex-col items-center py-16">
              <div className="text-4xl mb-4">
                {downloadResult.failed === 0 ? "✅" : "⚠️"}
              </div>
              <p className="text-lg font-bold text-slate-200 mb-2">下载任务完成</p>
              <div className="flex items-center gap-6 text-sm">
                <span className="text-green-400">成功 {downloadResult.success} 个</span>
                {downloadResult.failed > 0 && (
                  <span className="text-red-400">失败 {downloadResult.failed} 个</span>
                )}
              </div>
              <button
                onClick={onClose}
                className="mt-6 px-6 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-sm transition-colors"
              >
                关闭
              </button>
            </div>
          )}
        </div>

        {/* 底部操作栏（review 阶段显示） */}
        {phase === "review" && (
          <div className="p-4 border-t border-slate-700 flex items-center gap-3">
            {/* 下载通道选择 */}
            <span className="text-xs text-slate-400">下载通道：</span>
            <div className="flex gap-1">
              <button
                onClick={() => setDownloadChannel("qb")}
                disabled={!qbConfigured}
                title={qbConfigured ? "qBittorrent" : "qBittorrent 未配置"}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  downloadChannel === "qb" && qbConfigured
                    ? "bg-blue-600 text-white"
                    : qbConfigured
                    ? "bg-slate-700 text-slate-400 hover:bg-slate-600"
                    : "bg-slate-700 text-slate-500 cursor-not-allowed"
                }`}
              >
                qBittorrent
              </button>
              <button
                onClick={() => setDownloadChannel("alist")}
                disabled={!alistConfigured}
                title={alistConfigured ? "OpenList" : "OpenList 未配置"}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  downloadChannel === "alist" && alistConfigured
                    ? "bg-emerald-600 text-white"
                    : alistConfigured
                    ? "bg-slate-700 text-slate-400 hover:bg-slate-600"
                    : "bg-slate-700 text-slate-500 cursor-not-allowed"
                }`}
              >
                OpenList
              </button>
            </div>

            <div className="flex-1" />

            <span className="text-xs text-slate-500">
              已确认 {confirmedCount} 个
            </span>
            <button
              onClick={handleDownloadAll}
              disabled={confirmedCount === 0}
              className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-bold transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              全部下载
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── 状态图标小组件 ──
function StatusIcon({ status }: { status: BatchUpgradeTask["status"] }) {
  switch (status) {
    case "searching":
      return (
        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-400 flex-shrink-0" />
      );
    case "found":
      return <span className="text-green-400 flex-shrink-0">✓</span>;
    case "not_found":
      return <span className="text-slate-500 flex-shrink-0">✗</span>;
    case "error":
      return <span className="text-red-400 flex-shrink-0">⚠</span>;
    default:
      return <span className="text-slate-600 flex-shrink-0">○</span>;
  }
}
