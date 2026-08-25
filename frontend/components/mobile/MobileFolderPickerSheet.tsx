// 全屏目录选择 sheet（走 /fs/list）。
//
// 复用桌面 FolderPicker 的**数据契约**，不复用它的渲染层：那是 max-w-2xl 居中弹窗，
// 每行的「选这个」按钮是 opacity-0 group-hover:opacity-100 —— 触屏没有 hover，
// 用户根本点不到。这里整行可点，选中操作是独立的大按钮。
//
// 注意 /fs/list 按设计不受媒体库白名单约束（用户正要浏览白名单外的目录来添加媒体库），
// 会列出服务端全部盘符。这也是「前端端口不能暴露到公网」的原因之一。
"use client";
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";

export interface MobileFolderPickerSheetProps {
  open: boolean;
  onClose: () => void;
  /** 确认选择时回调 */
  onSelect: (path: string) => void;
  /** 打开时的起始目录 */
  initialPath?: string;
}

interface DirItem {
  name: string;
  path: string;
}

export default function MobileFolderPickerSheet({
  open, onClose, onSelect, initialPath = "",
}: MobileFolderPickerSheetProps) {
  const [cwd, setCwd] = useState("");
  const [parent, setParent] = useState("");
  const [dirs, setDirs] = useState<DirItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async (path: string) => {
    setLoading(true);
    setError("");
    try {
      const res = await api.listDirectories(path);
      // res.path 是服务端认定的当前目录（空串 = 根列表），用它显示而不是用请求参数
      setCwd(res.path);
      setParent(res.parent);
      setDirs(res.dirs || []);
      setError(res.error || "");
      if (listRef.current) listRef.current.scrollTop = 0;
    } catch (e) {
      setError(`读取目录失败：${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    void load(initialPath || "");
  }, [open, initialPath, load]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex flex-col bg-[var(--m-bg)]"
      role="dialog"
      aria-modal="true"
      aria-label="选择保存目录"
    >
      <header
        className="flex flex-shrink-0 items-center gap-2 border-b"
        style={{
          paddingTop: "var(--m-safe-top)",
          paddingLeft: "var(--m-page-px)",
          paddingRight: "var(--m-page-px)",
          borderColor: "var(--m-border)",
        }}
      >
        <button
          type="button"
          onClick={onClose}
          className="-ml-2 text-sm text-[var(--m-text-muted)]"
          style={{ minWidth: "var(--m-touch-min)", minHeight: "var(--m-touch-min)" }}
        >
          取消
        </button>
        <h2 className="min-w-0 flex-1 truncate text-center text-[15px] font-semibold text-[var(--m-text)]">
          选择目录
        </h2>
        <button
          type="button"
          onClick={() => { onSelect(cwd); onClose(); }}
          disabled={!cwd}
          className="-mr-2 text-sm font-medium disabled:opacity-40"
          style={{
            minWidth: "var(--m-touch-min)",
            minHeight: "var(--m-touch-min)",
            color: "var(--m-accent)",
          }}
        >
          用这里
        </button>
      </header>

      {/* 当前位置 + 上一级。上一级也是独立大按钮，不依赖返回手势 */}
      <div
        className="flex flex-shrink-0 items-center gap-2 border-b py-2"
        style={{
          paddingLeft: "var(--m-page-px)",
          paddingRight: "var(--m-page-px)",
          borderColor: "var(--m-border)",
        }}
      >
        <button
          type="button"
          onClick={() => { void load(parent); }}
          disabled={!parent || loading}
          className="flex items-center rounded-lg px-3 text-xs disabled:opacity-30"
          style={{
            minHeight: "var(--m-touch-min)",
            background: "var(--m-surface-raised)",
            color: "var(--m-text-muted)",
          }}
        >
          上一级
        </button>
        <button
          type="button"
          onClick={() => { void load(""); }}
          disabled={loading}
          className="flex items-center rounded-lg px-3 text-xs disabled:opacity-30"
          style={{
            minHeight: "var(--m-touch-min)",
            background: "var(--m-surface-raised)",
            color: "var(--m-text-muted)",
          }}
        >
          根目录
        </button>
        <span className="min-w-0 flex-1 truncate text-right text-[11px] text-[var(--m-text-dim)]">
          {cwd || "选择一个盘符或根目录"}
        </span>
      </div>

      <div ref={listRef} className="flex-1 overflow-y-auto" style={{ paddingBottom: "var(--m-safe-bottom)" }}>
        {loading && (
          <p className="py-10 text-center text-sm text-[var(--m-text-muted)]">加载中…</p>
        )}

        {!loading && error && (
          <p
            className="m-3 rounded-[var(--m-radius)] p-3 text-xs"
            style={{ background: "var(--m-surface)", color: "var(--m-warning)" }}
            role="alert"
          >
            {error}
          </p>
        )}

        {!loading && !error && dirs.length === 0 && (
          <p className="py-10 text-center text-sm text-[var(--m-text-dim)]">
            这个目录下没有子文件夹
          </p>
        )}

        {!loading && dirs.map(dir => (
          <button
            key={dir.path}
            type="button"
            // 整行可点：触屏没有 hover，桌面那种"悬停才出现的选择按钮"点不到
            onClick={() => { void load(dir.path); }}
            className="flex w-full items-center gap-3 border-b text-left active:bg-[var(--m-surface-raised)]"
            style={{
              minHeight: "var(--m-touch-min)",
              paddingLeft: "var(--m-page-px)",
              paddingRight: "var(--m-page-px)",
              borderColor: "var(--m-border)",
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="1.5" style={{ color: "var(--m-accent)" }} aria-hidden="true">
              <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            <span className="min-w-0 flex-1 truncate py-3 text-sm text-[var(--m-text)]">{dir.name}</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" style={{ color: "var(--m-text-dim)" }} aria-hidden="true">
              <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        ))}
      </div>
    </div>
  );
}
