// 侧边栏目录树 — 搜索 + 折叠展开
"use client";
import React, { useState, useCallback, useMemo } from "react";
import type { FolderNode } from "@/types";

interface SidebarProps {
  tree: FolderNode | null;
  currentFolder: FolderNode | null;
  onNavigate: (node: FolderNode) => void;
  collapsed: boolean;
  onToggle: () => void;
  onOpenPlugins?: () => void;
}

export default function Sidebar({ tree, currentFolder, onNavigate, collapsed, onToggle, onOpenPlugins }: SidebarProps) {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const searchInputRef = React.useRef<HTMLInputElement>(null);

  const toggleExpand = useCallback((path: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedNodes(prev => {
      const n = new Set(prev);
      if (n.has(path)) n.delete(path); else n.add(path);
      return n;
    });
  }, []);

  const matchPaths = useMemo(() => {
    if (!search.trim() || !tree) return null;
    const q = search.toLowerCase();
    const paths = new Set<string>();
    const walk = (node: FolderNode, ancestors: string[]) => {
      const match = node.name.toLowerCase().includes(q);
      let childMatch = false;
      if (node.children) {
        for (const child of node.children) {
          if (walk(child, [...ancestors, node.path])) childMatch = true;
        }
      }
      if (match || childMatch) {
        paths.add(node.path);
        ancestors.forEach(p => paths.add(p));
        return true;
      }
      return false;
    };
    walk(tree, []);
    return paths;
  }, [search, tree]);

  const renderTree = (node: FolderNode, level: number = 0) => {
    if (matchPaths && !matchPaths.has(node.path)) return null;

    const isRoot = level === 0;
    const isActive = currentFolder?.path === node.path;
    const hasChildren = node.children && node.children.length > 0;
    // 根目录永远展开，子目录看 expandedNodes
    const isExpanded = isRoot ? true : (matchPaths ? true : expandedNodes.has(node.path));

    return (
      <div key={node.path}>
        <div onClick={() => onNavigate(node)}
          className={`group flex items-center gap-2 py-2 px-4 rounded-lg cursor-pointer text-[13px] transition-all ${
            isActive ? "bg-blue-500/10 text-blue-400" : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
          }`}
          style={{ paddingLeft: collapsed ? '0.75rem' : isRoot ? '1rem' : `${1 + (level - 1) * 0.9}rem` }}>
          {/* 根目录不显示展开箭头，也不占位 */}
          {!collapsed && !isRoot && hasChildren && (
            <button onClick={(e) => toggleExpand(node.path, e)}
              className="w-7 h-7 flex items-center justify-center text-slate-600 hover:text-slate-300 flex-shrink-0 transition-transform rounded-md hover:bg-white/5"
              style={{ transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="m9 5 7 7-7 7" /></svg>
            </button>
          )}
          {!collapsed && !isRoot && !hasChildren && <span className="w-7 flex-shrink-0" />}
          <span className="text-sm">{hasChildren ? "📂" : "📁"}</span>
          {!collapsed && (
            <span className={`truncate flex-1 ${isActive ? "font-semibold" : ""}`}>{node.name || "媒体库"}</span>
          )}
          {!collapsed && node.video_count > 0 && (
            <span className="text-[10px] text-slate-600 flex-shrink-0">{node.video_count}</span>
          )}
        </div>
        {!collapsed && hasChildren && isExpanded && (
          <div>{node.children!.map(child => renderTree(child, level + 1))}</div>
        )}
      </div>
    );
  };

  return (
    <aside className={`h-screen bg-[#141414] border-r border-white/[0.06] flex flex-col transition-all duration-300 ${collapsed ? "w-16" : "w-64"}`}>
      <div className="p-3 flex flex-col items-center gap-2 border-b border-white/[0.06]">
        {collapsed ? (
          <>
            <button onClick={onToggle}
              className="w-10 h-10 rounded-lg flex items-center justify-center text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-all">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="m9 5 7 7-7 7" /></svg>
            </button>
            <button onClick={() => { onToggle(); setTimeout(() => searchInputRef.current?.focus(), 350); }}
              className="w-10 h-10 rounded-lg flex items-center justify-center text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-all">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" /></svg>
            </button>
          </>
        ) : (
          <div className="flex items-center gap-2 w-full">
            <div className="flex-1 relative">
              <svg className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" /></svg>
              <input ref={searchInputRef} value={search} onChange={e => setSearch(e.target.value)} placeholder="搜索目录..."
                className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-300 outline-none focus:border-blue-500/30 placeholder:text-slate-600" />
            </div>
            <button onClick={onToggle} className="w-10 h-10 rounded-lg bg-white/[0.04] flex items-center justify-center text-slate-500 hover:text-slate-300 hover:bg-white/10 transition-all flex-shrink-0">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="m15 19-7-7 7-7" /></svg>
            </button>
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto py-2 px-1">
        {tree ? renderTree(tree) : (
          <div className="p-6 text-center opacity-30">
            <span className="text-2xl block mb-2">📂</span>
            {!collapsed && <p className="text-xs text-slate-500">加载中...</p>}
          </div>
        )}
      </div>

      {/* 插件中心入口 */}
      <div className="border-t border-white/[0.06] p-2">
        <button onClick={onOpenPlugins}
          className={`w-full flex items-center gap-2 py-2.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-all ${collapsed ? "justify-center px-2" : "px-3"}`}>
          <span className="text-sm">🧩</span>
          {!collapsed && <span className="text-xs">插件中心</span>}
        </button>
      </div>
    </aside>
  );
}
