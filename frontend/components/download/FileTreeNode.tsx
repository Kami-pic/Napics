/* 文件树节点组件：用于整理替换三栏的树状展示 */
"use client";
import { useState } from "react";

export interface TreeNode {
  name: string;
  type: string;        // "root" | "dir" | "video" | "subtitle" | "file" | "other"
  size_bytes?: number;
  category?: string;   // 旧资源栏: "video" | "folder" | "non_video"
  action?: string;     // 标准化栏: "rename" | "skip" | "keep" | "create"
  skip_reason?: string;
  original_name?: string;
  children?: TreeNode[];
}

const ICONS: Record<string, string> = {
  root: "📂", dir: "📁", video: "🎬", subtitle: "💬", file: "📄", other: "📎",
};

const ACTION_COLORS: Record<string, string> = {
  rename: "text-green-400/60",
  skip: "text-yellow-500/60",
  keep: "text-slate-500/60",
  create: "text-blue-400/60",
};

const CATEGORY_COLORS: Record<string, string> = {
  video: "bg-red-500/10 text-red-400/70",
  folder: "bg-yellow-500/10 text-yellow-500/70",
  non_video: "bg-slate-500/10 text-slate-400/70",
};

function formatSize(bytes?: number): string {
  if (!bytes || bytes <= 0) return "";
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024 / 1024).toFixed(1)}GB`;
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(0)}MB`;
  return `${(bytes / 1024).toFixed(0)}KB`;
}

function getFileType(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  if (["mkv","mp4","avi","mov","wmv","rmvb","ts","m4v","flv","rm"].includes(ext)) return "video";
  if (["ass","srt","ssa","sub","idx","sup"].includes(ext)) return "subtitle";
  return "other";
}


interface FileTreeNodeProps {
  node: TreeNode;
  depth?: number;
  variant?: "old" | "new" | "plan";  // 三栏不同的配色方案
}

export function FileTreeNode({ node, depth = 0, variant = "new" }: FileTreeNodeProps) {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = node.children && node.children.length > 0;
  const isDir = node.type === "dir" || node.type === "root";
  const icon = ICONS[node.type] || ICONS[getFileType(node.name)] || "·";
  const sizeStr = formatSize(node.size_bytes);

  // 标签
  const tags: { text: string; cls: string }[] = [];
  if (sizeStr) tags.push({ text: sizeStr, cls: "text-slate-600" });

  if (variant === "old" && node.category) {
    const label = node.category === "video" ? "🗑 待清理" : node.category === "non_video" ? "⚠️ 保留" : "📁 含视频";
    const cls = CATEGORY_COLORS[node.category] || "";
    tags.push({ text: label, cls });
  }
  if (variant === "new") {
    const ft = node.type === "video" ? "video" : node.type === "subtitle" ? "subtitle" : (isDir ? "" : getFileType(node.name));
    if (ft === "video") tags.push({ text: "视频", cls: "bg-green-500/10 text-green-500/60" });
    else if (ft === "subtitle") tags.push({ text: "字幕", cls: "bg-yellow-500/10 text-yellow-500/60" });
    else if (ft && !isDir) tags.push({ text: node.name.split(".").pop() || "", cls: "bg-slate-500/10 text-slate-500/60" });
  }
  if (variant === "plan" && node.action) {
    const actionLabel = node.action === "rename" ? "✅ 重命名" : node.action === "skip" ? "⏭ 跳过" : node.action === "create" ? "📁 新建" : "";
    if (actionLabel) tags.push({ text: actionLabel, cls: ACTION_COLORS[node.action] || "" });
    if (node.skip_reason) tags.push({ text: node.skip_reason, cls: "text-yellow-500/50" });
  }

  // 子节点统计
  const childCount = hasChildren ? node.children!.length : 0;

  // 卡片底色
  const cardBg = variant === "old"
    ? (node.category === "non_video" ? "bg-yellow-500/[0.03] border-yellow-500/10" : "bg-white/[0.02] border-white/[0.03]")
    : variant === "plan"
      ? (node.action === "skip" ? "bg-yellow-500/[0.03] border-yellow-500/10" : "bg-blue-500/5 border-blue-500/10")
      : "bg-white/[0.02] border-white/[0.03]";

  // 标题颜色
  const titleCls = variant === "plan" && node.action === "rename"
    ? "text-blue-300"
    : variant === "plan" && node.action === "skip"
      ? "text-yellow-400/70"
      : variant === "old" && node.category === "non_video"
        ? "text-slate-500"
        : "text-slate-300";

  return (
    <div style={{ marginLeft: depth > 0 ? 12 : 0 }}>
      {/* 卡片 */}
      <div
        className={`${cardBg} p-2.5 rounded-lg border mb-1.5 ${isDir && hasChildren ? "cursor-pointer" : ""}`}
        onClick={isDir && hasChildren ? () => setExpanded(!expanded) : undefined}
      >
        <div className="flex items-center gap-1.5">
          {/* 展开箭头 */}
          {isDir && hasChildren && (
            <span className="text-[9px] text-slate-600 w-3 shrink-0 select-none">{expanded ? "▼" : "▶"}</span>
          )}
          {!isDir && depth > 0 && <span className="w-3 shrink-0" />}
          {/* 图标 + 标题 */}
          <span className="text-[10px] shrink-0">{icon}</span>
          <p className={`text-[10px] font-medium truncate font-mono flex-1 ${titleCls}`} title={node.name}>
            {node.name}
          </p>
        </div>
        {/* 副标题行：大小 + 标签 */}
        {tags.length > 0 && (
          <div className="flex items-center gap-2 mt-1 ml-[18px]">
            {tags.map((t, i) => (
              <span key={i} className={`text-[8px] px-1.5 py-0.5 rounded ${t.cls}`}>{t.text}</span>
            ))}
            {isDir && childCount > 0 && (
              <span className="text-[8px] text-slate-600">{childCount} 项</span>
            )}
          </div>
        )}
        {/* plan 栏：原始文件名 */}
        {variant === "plan" && node.original_name && node.original_name !== node.name && (
          <p className="text-[8px] text-slate-600 mt-1 ml-[18px] truncate font-mono" title={node.original_name}>
            ← {node.original_name}
          </p>
        )}
      </div>
      {/* 子节点 */}
      {expanded && hasChildren && (
        <div className="ml-1 border-l border-white/[0.04] pl-1">
          {node.children!.map((child, i) => (
            <FileTreeNode key={i} node={child} depth={depth + 1} variant={variant} />
          ))}
        </div>
      )}
    </div>
  );
}

interface FileTreeProps {
  tree: TreeNode[];
  variant?: "old" | "new" | "plan";
}

export function FileTree({ tree, variant = "new" }: FileTreeProps) {
  if (!tree || tree.length === 0) return <p className="text-[10px] text-slate-600 text-center py-4">无数据</p>;
  return (
    <div className="space-y-1">
      {tree.map((node, i) => (
        <FileTreeNode key={i} node={node} depth={0} variant={variant} />
      ))}
    </div>
  );
}
