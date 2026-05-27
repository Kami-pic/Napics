"use client";
import { useState } from "react";
import type { FolderNode, VideoInfo } from "@/types";
import { api } from "@/lib/api";

interface MovieCollectionGridProps {
  node: FolderNode;
  onSelectItem: (child: FolderNode | VideoInfo) => void;
}

export default function MovieCollectionGrid({ node, onSelectItem }: MovieCollectionGridProps) {
  const items = node.children.length > 0
    ? node.children.map(c => ({ type: "folder" as const, name: c.name, path: c.path, node: c, video: c.videos[0] }))
    : node.videos.map(v => ({ type: "video" as const, name: v.file_name, path: v.file_path, node: null, video: v }));

  return (
    <div className="grid grid-cols-2 gap-2">
      {items.map(item => (
        <button
          key={item.path}
          onClick={() => onSelectItem(item.type === "folder" ? item.node! : item.video)}
          className="bg-white/[0.03] hover:bg-white/[0.06] rounded-lg overflow-hidden border border-transparent hover:border-white/[0.06] transition-all text-left"
        >
          <CardPoster path={item.path} name={item.name} />
          <div className="px-2 py-1.5">
            <p className="text-xs text-slate-300 truncate">{item.name}</p>
          </div>
        </button>
      ))}
      {items.length === 0 && <p className="col-span-2 text-xs text-slate-600 py-4 text-center">暂无内容</p>}
    </div>
  );
}

function CardPoster({ path, name }: { path: string; name: string }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const src = api.getLocalPoster(path);

  return (
    <div className="aspect-[2/3] bg-[#222] relative">
      {!loaded && !error && <div className="absolute inset-0 flex items-center justify-center"><span className="text-slate-700 text-2xl">🎬</span></div>}
      {error && <div className="absolute inset-0 flex items-center justify-center"><span className="text-slate-700 text-2xl">🎬</span></div>}
      <img
        src={src}
        alt={name}
        className={`w-full h-full object-cover transition-opacity ${loaded ? "opacity-100" : "opacity-0"}`}
        onLoad={() => setLoaded(true)}
        onError={() => setError(true)}
      />
    </div>
  );
}
