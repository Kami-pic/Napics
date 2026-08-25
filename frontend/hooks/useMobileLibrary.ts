// 移动端媒体库页的状态入口：把应用级树缓存 + 当前 path 变成"这一屏渲染什么"。
//
// 树本身由 MobileLibraryTreeProvider 缓存，这里**必须自己调 ensureLoaded()** ——
// Provider 挂在 app/m/layout.tsx 上，不会自动加载（否则 /m/search、/m/play 也会白拉整树）。
"use client";
import { useEffect, useMemo } from "react";

import type { FolderNode } from "@/types";
import { useMobileLibraryTree } from "@/components/mobile/MobileLibraryTreeProvider";
import { findNode, resolveLibraryView, type MobileLibraryView } from "@/lib/mobile/libraryNav";
import type { MobileViewState } from "@/components/mobile/MobileStateView";

export interface UseMobileLibraryResult {
  state: MobileViewState;
  /** 当前 path 对应的节点；找不到时为 null */
  node: FolderNode | null;
  /** node 为 null 时 view 也为 null，页面走 error 分支 */
  view: MobileLibraryView | null;
  /** 树加载失败与"路径不在树里"是两种错误，文案不同 */
  errorText: string;
  reload: () => Promise<void>;
}

const LOAD_FAILED_TEXT = "媒体库加载失败，检查后端是否在运行";
const NOT_IN_TREE_TEXT = "这个目录不在媒体库里，可能已被移动或删除。同步一次再试";

export function useMobileLibrary(path: string): UseMobileLibraryResult {
  const { tree, ready, loadFailed, ensureLoaded, reload } = useMobileLibraryTree();

  useEffect(() => {
    ensureLoaded();
  }, [ensureLoaded]);

  const node = useMemo(() => (ready && !loadFailed ? findNode(tree, path) : null), [tree, ready, loadFailed, path]);
  const view = useMemo(() => (node ? resolveLibraryView(node) : null), [node]);

  let state: MobileViewState = "ready";
  let errorText = "";
  if (!ready) {
    state = "loading";
  } else if (loadFailed) {
    state = "error";
    errorText = LOAD_FAILED_TEXT;
  } else if (!node) {
    state = "error";
    errorText = NOT_IN_TREE_TEXT;
  } else if (view?.isEmpty) {
    state = "empty";
  }

  return { state, node, view, errorText, reload };
}
