import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FolderDetail } from "@/components/detail/FolderDetail";

vi.mock("@/components/detail/useScrape", () => ({
  useScrape: () => ({
    data: null,
    loading: false,
    status: "idle",
    rescrape: vi.fn(),
    reload: vi.fn(),
    setData: vi.fn(),
    confidence: null,
    pendingConfirm: false,
    setPendingConfirm: vi.fn(),
  }),
}));

vi.mock("@/components/detail/PosterUpload", () => ({
  PosterUpload: ({ onUploaded }: { onUploaded: (deleted?: boolean) => void }) => (
    <button onClick={() => onUploaded(false)}>mock-poster-upload</button>
  ),
}));

vi.mock("@/components/detail/CandidatePicker", () => ({
  CandidatePicker: ({ onSelected }: { onSelected: (data: { title: string }) => void }) => (
    <button onClick={() => onSelected({ title: "军火女王" })}>mock-candidate-picker</button>
  ),
}));

vi.mock("@/components/detail/ShadowNameSection", () => ({
  ShadowNameSection: () => <div>shadow-name</div>,
}));

vi.mock("@/components/detail/CompletenessBar", () => ({
  CompletenessBar: () => <div>completeness</div>,
}));

vi.mock("@/components/detail/DetailComponents", () => ({
  Poster: () => <div>poster</div>,
  InfoRow: ({ label, value }: { label: string; value: string }) => <div>{label}:{value}</div>,
  MoveAction: () => <div>move</div>,
  CopyAction: () => <div>copy</div>,
  DeleteAction: () => <div>delete</div>,
  ConfidenceBadge: () => <div>confidence</div>,
  ScrapeInfo: () => <div>scrape</div>,
  ActionButton: ({ label, onClick }: { label: string; onClick: () => void }) => (
    <button onClick={onClick}>{label}</button>
  ),
}));

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    getNoScrape: vi.fn(),
  },
}));

vi.mock("@/lib/api", () => ({
  api: mockApi,
}));

describe("FolderDetail tree refresh", () => {
  beforeEach(() => {
    mockApi.getNoScrape.mockReset();
    mockApi.getNoScrape.mockResolvedValue([]);
    vi.restoreAllMocks();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  });

  it("文件夹封面上传后只触发树刷新", async () => {
    const onRefresh = vi.fn();
    const onTreeRefresh = vi.fn();

    render(
      <FolderDetail
        node={{
          name: "军火女王",
          path: "\\\\NAS\\视频\\动画番\\军火女王",
          folder_type: "tv",
          category_tag: "tv",
          videos: [],
          children: [],
          video_count: 0,
          has_cover: true,
        }}
        onRefresh={onRefresh}
        onTreeRefresh={onTreeRefresh}
        onSearch={vi.fn()}
        currentCategoryTag="tv"
      />,
    );

    fireEvent.click(screen.getByText("mock-poster-upload"));

    await waitFor(() => {
      expect(onTreeRefresh).toHaveBeenCalledTimes(1);
    });

    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("文件夹手动候选确认后只触发树刷新", async () => {
    const onRefresh = vi.fn();
    const onTreeRefresh = vi.fn();

    render(
      <FolderDetail
        node={{
          name: "军火女王",
          path: "\\\\NAS\\视频\\动画番\\军火女王",
          folder_type: "tv",
          category_tag: "tv",
          videos: [],
          children: [],
          video_count: 0,
          has_cover: true,
        }}
        onRefresh={onRefresh}
        onTreeRefresh={onTreeRefresh}
        onSearch={vi.fn()}
        currentCategoryTag="tv"
      />,
    );

    fireEvent.click(screen.getByText("mock-candidate-picker"));

    await waitFor(() => {
      expect(onTreeRefresh).toHaveBeenCalledTimes(1);
    });

    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("分类标签修改后只触发树刷新", async () => {
    const onRefresh = vi.fn();
    const onTreeRefresh = vi.fn();

    render(
      <FolderDetail
        node={{
          name: "动画番",
          path: "\\\\NAS\\视频\\动画番",
          folder_type: "tv",
          category_tag: "tv",
          is_virtual_library: true,
          videos: [],
          children: [],
          video_count: 0,
          has_cover: true,
        }}
        onRefresh={onRefresh}
        onTreeRefresh={onTreeRefresh}
        onSearch={vi.fn()}
        currentCategoryTag="tv"
      />,
    );

    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "movie" } });

    await waitFor(() => {
      expect(onTreeRefresh).toHaveBeenCalledTimes(1);
    });

    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("文件夹类型修改后只触发树刷新", async () => {
    const onRefresh = vi.fn();
    const onTreeRefresh = vi.fn();

    render(
      <FolderDetail
        node={{
          name: "军火女王",
          path: "\\\\NAS\\视频\\动画番\\军火女王",
          folder_type: "tv",
          category_tag: "tv",
          videos: [],
          children: [],
          video_count: 0,
          has_cover: true,
        }}
        onRefresh={onRefresh}
        onTreeRefresh={onTreeRefresh}
        onSearch={vi.fn()}
        currentCategoryTag="tv"
      />,
    );

    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "season" } });

    await waitFor(() => {
      expect(onTreeRefresh).toHaveBeenCalledTimes(1);
    });

    expect(onRefresh).not.toHaveBeenCalled();
  });
});
