import { describe, it, expect } from "vitest";

import { formatSize, sumFolderSize } from "@/lib/utils";

/** 造一个树节点，只带这个函数关心的字段 */
function node(videos: number[], children: any[] = []) {
  return {
    videos: videos.map(size_gb => ({ size_gb })),
    children,
  };
}

describe("文件夹大小", () => {
  it("累加当前层的视频", () => {
    expect(sumFolderSize(node([1.5, 2.5]))).toBeCloseTo(4);
  });

  it("递归含子目录 —— video_count 在后端是递归的，大小不递归就会自相矛盾", () => {
    const tree = node([1], [node([2]), node([3], [node([4])])]);
    expect(sumFolderSize(tree)).toBeCloseTo(10);
  });

  it("空节点是 0，不是 NaN", () => {
    expect(sumFolderSize({})).toBe(0);
    expect(sumFolderSize(node([]))).toBe(0);
  });

  it("size_gb 缺失的条目当 0 —— ffprobe 失败的记录没有这个字段", () => {
    const tree = { videos: [{ size_gb: 2 }, {}, { size_gb: undefined }], children: [] };
    expect(sumFolderSize(tree)).toBeCloseTo(2);
  });

  it("总大小 0 时格式化成占位符，不显示 0G", () => {
    expect(formatSize(sumFolderSize({}))).toBe("—");
  });
});
