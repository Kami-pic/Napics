// 返回上一级 + 面包屑路径
"use client";
import React, { useMemo } from "react";
import type { FolderNode } from "@/types";

interface BreadcrumbsProps {
  tree: FolderNode | null;
  currentFolder: FolderNode | null;
  onNavigate: (node: FolderNode) => void;
}

export default function Breadcrumbs({ tree, currentFolder, onNavigate }: BreadcrumbsProps) {
  const pathNodes = useMemo(() => {
    if (!tree || !currentFolder) return [];
    if (currentFolder.path === "") return [tree];
    const nodes: FolderNode[] = [];
    const findPath = (curr: FolderNode, targetPath: string, chain: FolderNode[]): boolean => {
      if (curr.path === targetPath) { nodes.push(...chain, curr); return true; }
      if (curr.children) {
        for (const child of curr.children) {
          if (findPath(child, targetPath, [...chain, curr])) return true;
        }
      }
      return false;
    };
    findPath(tree, currentFolder.path, []);
    return nodes.length > 0 ? nodes : [tree];
  }, [tree, currentFolder]);

  if (!tree || !currentFolder) return <div />;

  const isRoot = !currentFolder.path || currentFolder.path === "";
  // 上一级 = 面包屑倒数第二个
  const parent = pathNodes.length >= 2 ? pathNodes[pathNodes.length - 2] : null;

  return (
    <div className="flex items-center gap-2">
      {!isRoot && parent && (
        <button onClick={() => onNavigate(parent)}
          className="flex items-center gap-1 text-sm mr-1 text-slate-400 hover:text-white transition-all">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path d="M15 19l-7-7 7-7" /></svg>
          返回
        </button>
      )}
      <nav className="flex items-center gap-1.5 text-[15px] overflow-x-auto no-scrollbar">
        {pathNodes.map((node, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="text-slate-700">/</span>}
            <button onClick={() => onNavigate(node)}
              className={`whitespace-nowrap px-1 py-0.5 rounded transition-all ${
                i === pathNodes.length - 1 ? "text-white font-semibold" : "text-slate-500 hover:text-slate-300"
              }`}>
              {node.name === "Root" || node.name === "媒体库" || node.path === "" ? "媒体库" : node.name}
            </button>
          </React.Fragment>
        ))}
      </nav>
    </div>
  );
}
