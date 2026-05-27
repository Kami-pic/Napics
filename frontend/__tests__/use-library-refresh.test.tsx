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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

describe("useLibrary refreshTree", () => {
  beforeEach(() => {
    mockApi.getConfig.mockReset();
    mockApi.getLibrary.mockReset();
    mockApi.getLibraryTree.mockReset();

    mockApi.getConfig.mockResolvedValue({
      scan_paths: ["\\\\NAS\\视频"],
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

  it("全量刷新时目录树先返回即可先更新首页树", async () => {
    const library = deferred<any[]>();
    mockApi.getLibrary.mockReturnValue(library.promise);
    mockApi.getLibraryTree.mockResolvedValue(makeTree());

    const { result } = renderHook(() => useLibrary());

    await waitFor(() => {
      expect(result.current.fileTree?.children?.[0]?.name).toBe("动画番");
    });

    expect(result.current.videos).toEqual([]);

    await act(async () => {
      library.resolve([
        {
          file_path: "\\\\NAS\\视频\\动画番\\军火女王\\S01E01.mkv",
          file_name: "S01E01.mkv",
          folder_name: "军火女王",
          size_gb: 1,
          is_low_res: false,
          subtitle_count: 1,
        },
      ]);
      await library.promise;
    });

    await waitFor(() => {
      expect(result.current.videos).toHaveLength(1);
    });
  });
});
