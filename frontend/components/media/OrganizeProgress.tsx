// 一键整理进度反馈面板（SSE 流式 5 步进度）
"use client";
import { useState, useCallback, useEffect } from "react";
import { api } from "@/lib/api";
import type { OrganizeProgressEvent } from "@/types";

interface Props {
  open: boolean;
  path: string;
  onClose: () => void;
  onComplete: () => void;
}

const STEP_LABELS = ["", "散装视频封装", "旧刮削清理", "分析判定", "刮削确权", "结构归位"];

export default function OrganizeProgress({ open, path, onClose, onComplete }: Props) {
  const [events, setEvents] = useState<OrganizeProgressEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [completed, setCompleted] = useState(false);
  const [useAi, setUseAi] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(false);

  // 检查 AI 是否可用
  useEffect(() => {
    if (open) {
      api.getAIStatus().then(s => setAiEnabled(s.enabled && s.features?.extract_episode)).catch(() => setAiEnabled(false));
    }
  }, [open]);

  const startOrganize = useCallback(async (dryRun: boolean) => {
    setRunning(true);
    setError("");
    setCompleted(false);
    setEvents([]);

    try {
      const response = await api.organizeFullStream(path, dryRun, useAi);
      const reader = response.body?.getReader();
      if (!reader) return;

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
            const evt: OrganizeProgressEvent = JSON.parse(part.replace("data: ", ""));
            setEvents(prev => [...prev, evt]);
            if (evt.status === "completed") {
              setCompleted(true);
              onComplete();
            }
            if (evt.status === "error") {
              setError(evt.error || "未知错误");
            }
          } catch { /* skip */ }
        }
      }
    } catch (e: any) {
      setError(e.message || "连接失败");
    } finally {
      setRunning(false);
    }
  }, [path, onComplete]);

  if (!open) return null;

  const currentStep = events.filter(e => e.status === "done").length;
  const totalSteps = 5;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-8 z-50"
      onClick={(e) => { if (e.target === e.currentTarget && !running) onClose(); }}>
      <div className="bg-[var(--background)] border border-white/[0.06] rounded-2xl w-full max-w-lg p-6">
        <h2 className="text-base font-semibold text-white mb-4">一键整理</h2>
        <p className="text-xs text-slate-500 mb-4 font-mono truncate">{path}</p>

        {!running && !completed && !error && (
          <div className="space-y-3">
            {aiEnabled && (
              <label className="flex items-center gap-2 px-1 cursor-pointer">
                <input type="checkbox" checked={useAi} onChange={() => setUseAi(!useAi)}
                  className="w-3.5 h-3.5 rounded accent-blue-500" />
                <span className="text-xs text-slate-400">🤖 AI 辅助（乱码文件名自动识别）</span>
              </label>
            )}
            <div className="flex gap-3">
              <button onClick={() => startOrganize(true)}
                className="flex-1 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-xl text-sm font-medium transition-all">
                推演预览
              </button>
              <button onClick={() => startOrganize(false)}
                className="flex-1 py-2.5 bg-green-600 hover:bg-green-500 rounded-xl text-sm font-medium transition-all">
                直接执行
              </button>
            </div>
          </div>
        )}

        {(running || completed || error) && (
          <div className="space-y-3">
            {/* 进度条 */}
            <div className="flex items-center gap-3">
              <div className="flex-1 h-2 bg-white/[0.06] rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all duration-500"
                  style={{ width: `${(currentStep / totalSteps) * 100}%` }}
                />
              </div>
              <span className="text-xs text-slate-400">{currentStep}/{totalSteps}</span>
            </div>

            {/* 步骤列表 */}
            <div className="space-y-2">
              {Array.from({ length: totalSteps }, (_, i) => i + 1).map(step => {
                const doneEvt = events.find(e => e.step === step && e.status === "done");
                const runningEvt = events.find(e => e.step === step && e.status === "running");
                const isRunning = !!runningEvt && !doneEvt;
                const isDone = !!doneEvt;

                return (
                  <div key={step} className="flex items-center gap-3">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold
                      ${isDone ? "bg-green-500/20 text-green-400" : isRunning ? "bg-blue-500/20 text-blue-400" : "bg-white/[0.04] text-slate-600"}`}>
                      {isDone ? "✓" : isRunning ? (
                        <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                      ) : step}
                    </div>
                    <span className={`text-xs ${isDone ? "text-slate-300" : isRunning ? "text-blue-400" : "text-slate-600"}`}>
                      {STEP_LABELS[step]}
                    </span>
                    {doneEvt?.count !== undefined && (
                      <span className="text-[10px] text-slate-500 ml-auto">{doneEvt.count} 项</span>
                    )}
                    {doneEvt?.folder_type && (
                      <span className="text-[10px] text-slate-500 ml-auto">{doneEvt.folder_type}</span>
                    )}
                    {doneEvt?.result?.ai_parsed_count > 0 && (
                      <span className="text-[10px] text-blue-400 ml-1">🤖 {doneEvt?.result?.ai_parsed_count}</span>
                    )}
                    {doneEvt?.result?.ai_selected_count > 0 && (
                      <span className="text-[10px] text-blue-400 ml-1">🤖 {doneEvt?.result?.ai_selected_count}</span>
                    )}
                  </div>
                );
              })}
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-xs text-red-400">
                {error}
              </div>
            )}

            {completed && (
              <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3 text-xs text-green-400">
                整理完成
              </div>
            )}

            {!running && (
              <button onClick={onClose}
                className="w-full py-2.5 bg-white/[0.06] hover:bg-white/[0.08] rounded-xl text-sm text-slate-400 transition-all mt-2">
                关闭
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
