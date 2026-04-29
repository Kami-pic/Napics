import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { useLibrary } from "@/hooks/useLibrary";

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    getConfig: vi.fn(),
    getLibrary: vi.fn(),
    getLibraryTree: vi.fn(),
  },
}));

vi.mock("@/lib/api", () => ({
  api: mockApi,
}));

function makeTree() {
  return {
    name: "媒体库",
    path: "",
    videos: [],
    video_count: 1,
    has_cover: true,
    children: [
      {
        name: "动画番",
        path: "\\\\NAS\\视频\\动画番",
        videos: [],
        video_count: 1,
        has_cover: true,
        children: [],
      },
    ],
  };
}

describe("useLibrary refreshTree", () => {
  beforeEach(() => {
    mockApi.getConfig.mockReset();
    mockApi.getLibrary.mockReset();
    mockApi.getLibraryTree.mockReset();

    mockApi.getConfig.mockResolvedValue({
      nas_paths: ["\\\\NAS\\视频"],
    });
    mockApi.getLibrary.mockResolvedValue([]);
    mockApi.getLibraryTree.mockResolvedValue(makeTree());
  });

  it("只刷新目录树，不重复拉取全量视频列表", async () => {
    const { result } = renderHook(() => useLibrary());

    await waitFor(() => {
      expect(mockApi.getLibrary).toHaveBeenCalledTimes(1);
      expect(mockApi.getLibraryTree).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      await result.current.refreshTree();
    });

    expect(mockApi.getLibrary).toHaveBeenCalledTimes(1);
    expect(mockApi.getLibraryTree).toHaveBeenCalledTimes(2);
    expect(result.current.fileTree?.children?.[0]?.name).toBe("动画番");
  });
});
