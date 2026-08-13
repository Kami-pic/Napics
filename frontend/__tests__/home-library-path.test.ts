import { describe, expect, it } from "vitest";

import { findLibraryNodeByPath } from "@/app/page";
import type { FolderNode } from "@/types";

function makeTree(): FolderNode {
  return {
    name: "媒体库",
    path: "",
    videos: [],
    video_count: 2,
    has_cover: true,
    children: [
      {
        name: "动画番",
        path: "\\\\NAS\\share\\视频\\动画番",
        videos: [],
        video_count: 2,
        has_cover: true,
        children: [
          {
            name: "军火女王 Jormungand",
            path: "\\\\NAS\\share\\视频\\动画番\\军火女王 Jormungand",
            videos: [],
            video_count: 1,
            has_cover: true,
            children: [],
          },
          {
            name: "卡罗尔与星期二 CAROLE & TUESDAY",
            path: "\\\\NAS\\share\\视频\\动画番\\卡罗尔与星期二 CAROLE & TUESDAY",
            videos: [],
            video_count: 1,
            has_cover: true,
            children: [],
          },
        ],
      },
    ],
  };
}

describe("findLibraryNodeByPath", () => {
  it("优先命中绝对 NAS 路径", () => {
    const tree = makeTree();
    const node = findLibraryNodeByPath(tree, "\\\\NAS\\share\\视频\\动画番\\军火女王 Jormungand", ["\\\\NAS\\share\\视频"]);
    expect(node?.name).toBe("军火女王 Jormungand");
  });

  it("在大小写和斜杠不一致时仍能回退命中", () => {
    const tree = makeTree();
    const node = findLibraryNodeByPath(tree, "//NAS/share/视频/动画番/卡罗尔与星期二 CAROLE & TUESDAY/", ["\\\\NAS\\share\\视频"]);
    expect(node?.name).toBe("卡罗尔与星期二 CAROLE & TUESDAY");
  });
});
