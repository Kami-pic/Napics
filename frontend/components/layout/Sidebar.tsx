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
  onOpenSettings?: () => void;
  showDiscover?: boolean;
  onScrollToDiscover?: () => void;
  activeSection?: "library" | "discover";
}

export default function Sidebar({ tree, currentFolder, onNavigate, collapsed, onToggle, onOpenPlugins, onOpenSettings, showDiscover, onScrollToDiscover, activeSection }: SidebarProps) {
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
          className={`group flex items-center gap-2 py-2 rounded-lg cursor-pointer text-[13px] transition-all ${
            // 折叠态只剩一个图标，用 justify-center + px-2 与底部「发现/插件/设置」
            // 三个按钮取同一套写法，否则图标会靠左、和下面的对不齐。
            // px-3 与底部三个按钮一致（左侧再由 style.paddingLeft 按层级缩进覆盖）
            collapsed ? "justify-center px-2" : "px-3"
          } ${
            // 选中态只变文字颜色，不铺底色 —— 底色块的左右边距受容器 padding 影响，
            // 和底部「发现/插件/设置」那几个按钮对不齐，视觉上像是错位。
            // 不铺底色，但 hover 反馈必须保留 —— 选中项也要能 hover，
            // 否则鼠标移上去毫无反应，看着像不可点。
            isActive
              ? "text-blue-400 font-medium hover:bg-white/5"
              : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
          }`}
          // 根节点起点 0.75rem = px-3，和底部按钮左边距对齐；子层级从这里往右缩进
          style={collapsed ? undefined : { paddingLeft: isRoot ? '0.75rem' : `${0.75 + (level - 1) * 0.9}rem` }}>
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
      {/* px-2 与下面「发现 / 插件 / 设置」三个区块的容器一致，否则同样宽度的
          行在这里和那里的左右边距差 4px */}
      <div className="flex-1 overflow-y-auto py-2 px-2">
        {tree ? renderTree(tree) : (
          <div className="p-6 text-center opacity-30">
            <span className="text-2xl block mb-2">📂</span>
            {!collapsed && <p className="text-xs text-slate-500">加载中...</p>}
          </div>
        )}
      </div>

      {/* 区域导航（发现插件安装时显示） */}
      {showDiscover && (
        <div className="border-t border-white/[0.06] px-2 py-2">
          <button onClick={onScrollToDiscover}
            className={`w-full flex items-center gap-2 py-2 rounded-lg text-[13px] transition-all ${collapsed ? "justify-center px-2" : "px-3"} ${
              // 与目录树选中态同一套：只变文字颜色，不铺底色
              activeSection === "discover"
                ? "text-blue-400 font-medium hover:bg-white/5"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
            }`}>
            <span className="text-sm">🎬</span>
            {!collapsed && <span>发现</span>}
          </button>
        </div>
      )}

      {/* 插件中心 + 设置入口 */}
      <div className="border-t border-white/[0.06] px-2 py-3 space-y-1.5">
        <button onClick={onOpenPlugins}
          className={`w-full flex items-center gap-2 py-2 rounded-lg text-[13px] text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-all ${collapsed ? "justify-center px-2" : "px-3"}`}>
          <span className="text-sm">🧩</span>
          {!collapsed && <span>插件</span>}
        </button>
        <button onClick={onOpenSettings}
          className={`w-full flex items-center gap-2 py-2 rounded-lg text-[13px] text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-all ${collapsed ? "justify-center px-2" : "px-3"}`}>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" /><circle cx="12" cy="12" r="3" /></svg>
          {!collapsed && <span>设置</span>}
        </button>
      </div>
    </aside>
  );
}
