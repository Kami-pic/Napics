// 保存路径三段交互：Config 默认值预填 + 全屏目录选择 + 手动输入 + 可达校验。
//
// checkPath 只提示不拦截：Docker 部署时用户填宿主机路径是最常见的错误，
// 但校验本身也可能因后端临时不可用而失败，拦着不让提交只会把人卡死。
"use client";
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import MobileFolderPickerSheet from "./MobileFolderPickerSheet";

/** 手输防抖，和桌面 PathInput 保持一致 */
const CHECK_DEBOUNCE_MS = 600;

type CheckState =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "ok" }
  | { kind: "warn"; hint: string };

export interface MobileSavePathFieldProps {
  value: string;
  onChange: (path: string) => void;
  /** Config 里的默认扫描路径，用于占位提示 */
  defaultPath?: string;
  label?: string;
}

export default function MobileSavePathField({
  value, onChange, defaultPath = "", label = "保存到",
}: MobileSavePathFieldProps) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const [check, setCheck] = useState<CheckState>({ kind: "idle" });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const runCheck = useCallback(async (path: string) => {
    abortRef.current?.abort();
    if (!path.trim()) {
      setCheck({ kind: "idle" });
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setCheck({ kind: "checking" });
    try {
      const res = await api.checkPath(path.trim());
      if (controller.signal.aborted) return;
      if (res.exists && res.is_dir && res.readable) {
        setCheck({ kind: "ok" });
      } else {
        setCheck({ kind: "warn", hint: res.hint || "服务端访问不到这个目录" });
      }
    } catch {
      if (controller.signal.aborted) return;
      // 校验请求本身失败 ≠ 路径不可用，别把它说成路径有问题
      setCheck({ kind: "warn", hint: "无法校验这个路径，提交前请自行确认" });
    }
  }, []);

  // 值变化后防抖校验（选目录回填和手输都会走到这里）
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => { void runCheck(value); }, CHECK_DEBOUNCE_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [value, runCheck]);

  useEffect(() => {
    const controller = abortRef;
    return () => controller.current?.abort();
  }, []);

  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs text-[var(--m-text-muted)]">{label}</span>
      <div className="flex items-stretch gap-2">
        <input
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={defaultPath || "输入或选择保存目录"}
          aria-label="保存目录"
          className="min-w-0 flex-1 rounded-[var(--m-radius)] border px-3 text-sm outline-none"
          style={{
            minHeight: "var(--m-touch-min)",
            background: "var(--m-surface)",
            borderColor: "var(--m-border)",
            color: "var(--m-text)",
          }}
        />
        <button
          type="button"
          onClick={() => setSheetOpen(true)}
          className="flex-shrink-0 rounded-[var(--m-radius)] px-4 text-sm"
          style={{
            minHeight: "var(--m-touch-min)",
            background: "var(--m-surface-raised)",
            color: "var(--m-text)",
          }}
        >
          浏览
        </button>
      </div>

      {check.kind === "checking" && (
        <p className="text-[11px] text-[var(--m-text-dim)]">正在检查服务端能否访问…</p>
      )}
      {check.kind === "ok" && (
        <p className="text-[11px]" style={{ color: "var(--m-success)" }}>服务端可以访问这个目录</p>
      )}
      {check.kind === "warn" && (
        // 只是提示：仍然允许提交
        <p className="text-[11px]" style={{ color: "var(--m-warning)" }}>{check.hint}</p>
      )}

      <MobileFolderPickerSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        initialPath={value || defaultPath}
        onSelect={picked => onChange(picked)}
      />
    </div>
  );
}
