// 前端拆分组件回归测试
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// ── SearchModal 拆分组件 ──

describe("EpisodeTable", () => {
  it("渲染逐集表格 + 方案对比", async () => {
    const { default: EpisodeTable } = await import(
      "@/components/search/EpisodeTable"
    );
    const episodeResults = {
      1: {
        episode: 1,
        status: "found" as const,
        recommended: {
          title: "Test S01E01",
          size_gb: 1.5,
          indexer: "test",
          seeders: 10,
          leechers: 2,
          download_url: "magnet:?xt=test",
          quality_tag: "1080p",
          quality: {
            resolution: "1080p", source: "WEB-DL", video_codec: "x265",
            audio_codec: "AAC", has_chinese_sub: true, release_group: "GRP",
            is_surround: false, display: "1080p WEB-DL x265",
          },
          quality_rank: 5,
        },
        alternatives: [],
      },
      2: { episode: 2, status: "not_found" as const, recommended: null, alternatives: [] },
    };
    const seasonPacks = [
      {
        result: {
          title: "Pack", size_gb: 10, indexer: "t", seeders: 5, leechers: 1,
          download_url: "magnet:?xt=pack", quality_tag: "1080p",
          quality: { resolution: "1080p", source: "", video_codec: "", audio_codec: "", has_chinese_sub: false, release_group: "", is_surround: false, display: "1080p" },
          quality_rank: 5,
        },
        verification: { verified: true, is_magnet: true, episode_count: 2, episodes_found: [1, 2], is_complete: true },
      },
    ];

    render(
      <EpisodeTable
        episodeResults={episodeResults}
        seasonPacks={seasonPacks}
        totalSizePack={10}
        totalSizeEpisode={1.5}
        recommendedPlan="season_pack"
        onSelectAlternative={vi.fn()}
      />
    );

    expect(screen.getByText("整季包方案")).toBeInTheDocument();
    expect(screen.getByText("逐集拼凑方案")).toBeInTheDocument();
    expect(screen.getByText("E01")).toBeInTheDocument();
    expect(screen.getByText("E02")).toBeInTheDocument();
    expect(screen.getByText("⚠ 缺失")).toBeInTheDocument();
  });
});

describe("PanFilterBar", () => {
  it("导出 PanFilterState / DEFAULT_PAN_FILTERS / applyPanFilters", async () => {
    const mod = await import("@/components/search/PanFilterBar");
    expect(mod.DEFAULT_PAN_FILTERS).toBeDefined();
    expect(mod.DEFAULT_PAN_FILTERS.panType).toBe("");
    expect(mod.applyPanFilters).toBeTypeOf("function");
    expect(mod.PAN_TYPE_COLORS).toBeDefined();
    expect(mod.PAN_TYPE_LABELS).toBeDefined();
    expect(mod.SOURCE_LABELS).toBeDefined();
  });

  it("applyPanFilters 按网盘类型筛选", async () => {
    const { applyPanFilters } = await import("@/components/search/PanFilterBar");
    const results = [
      { pan_type: "quark", source: "pansearch", resolution: "1080p", is_complete: true },
      { pan_type: "aliyun", source: "pansou", resolution: "2160p", is_complete: false },
    ] as any;

    const filtered = applyPanFilters(results, { panType: "quark", source: "", resolution: "", completeOnly: false });
    expect(filtered).toHaveLength(1);
    expect(filtered[0].pan_type).toBe("quark");
  });

  it("applyPanFilters 仅整季筛选", async () => {
    const { applyPanFilters } = await import("@/components/search/PanFilterBar");
    const results = [
      { pan_type: "quark", source: "s", resolution: "", is_complete: true },
      { pan_type: "aliyun", source: "s", resolution: "", is_complete: false },
    ] as any;

    const filtered = applyPanFilters(results, { panType: "", source: "", resolution: "", completeOnly: true });
    expect(filtered).toHaveLength(1);
    expect(filtered[0].is_complete).toBe(true);
  });

  it("渲染筛选栏", async () => {
    const { default: PanFilterBar, DEFAULT_PAN_FILTERS } = await import(
      "@/components/search/PanFilterBar"
    );
    render(
      <PanFilterBar
        filters={DEFAULT_PAN_FILTERS}
        onChange={vi.fn()}
        groups={{ quark: [] }}
        sourceStatuses={[]}
      />
    );
    expect(screen.getByText("网盘")).toBeInTheDocument();
    expect(screen.getByText("来源")).toBeInTheDocument();
    expect(screen.getByText("分辨率")).toBeInTheDocument();
    expect(screen.getByText("仅整季")).toBeInTheDocument();
  });
});

describe("PanResultsView", () => {
  it("搜索中显示 loading", async () => {
    const { default: PanResultsView } = await import(
      "@/components/search/PanResultsView"
    );
    render(
      <PanResultsView
        searching={true}
        groups={{}}
        total={0}
        sourceStatuses={[]}
        keyword="test"
        filters={{ panType: "", source: "", resolution: "", completeOnly: false }}
        onRetry={vi.fn()}
        onTransfer={vi.fn()}
      />
    );
    expect(screen.getByText("搜索网盘资源...")).toBeInTheDocument();
  });

  it("无结果显示重试按钮", async () => {
    const { default: PanResultsView } = await import(
      "@/components/search/PanResultsView"
    );
    const onRetry = vi.fn();
    render(
      <PanResultsView
        searching={false}
        groups={{}}
        total={0}
        sourceStatuses={[]}
        keyword="test"
        filters={{ panType: "", source: "", resolution: "", completeOnly: false }}
        onRetry={onRetry}
        onTransfer={vi.fn()}
      />
    );
    expect(screen.getByText("未搜到网盘资源")).toBeInTheDocument();
    fireEvent.click(screen.getByText("重试"));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

// ── CardGrid 拆分组件 ──

describe("CardPoster", () => {
  it("无 path 时显示占位图标", async () => {
    const { default: CardPoster } = await import(
      "@/components/media/CardPoster"
    );
    render(<CardPoster name="测试电影" />);
    expect(screen.getByText("🎬")).toBeInTheDocument();
  });
});

describe("EpisodeList", () => {
  it("渲染视频列表", async () => {
    const { default: EpisodeList } = await import(
      "@/components/media/EpisodeList"
    );
    const videos = [
      {
        file_name: "测试剧 S01E01.mkv", file_path: "/test/s01e01.mkv",
        folder_name: "测试剧", size_gb: 1.2, resolution: "1080p",
        width: 1920, height: 1080, duration: 45, audio_codec: "AAC",
        video_codec: "x265", subtitle_count: 1, hdr_type: "", is_low_res: false,
      },
      {
        file_name: "测试剧 S01E02.mkv", file_path: "/test/s01e02.mkv",
        folder_name: "测试剧", size_gb: 1.3, resolution: "1080p",
        width: 1920, height: 1080, duration: 44, audio_codec: "AAC",
        video_codec: "x265", subtitle_count: 0, hdr_type: "", is_low_res: false,
      },
    ];
    render(
      <EpisodeList
        videos={videos}
        selectedPaths={new Set()}
        onToggleSelect={vi.fn()}
        onPlay={vi.fn()}
        onSearch={vi.fn()}
        onVideoDetail={vi.fn()}
      />
    );
    expect(screen.getByText("测试剧 S01E01.mkv")).toBeInTheDocument();
    expect(screen.getByText("测试剧 S01E02.mkv")).toBeInTheDocument();
    expect(screen.getAllByText("1080p")).toHaveLength(2);
  });

  it("空列表显示提示", async () => {
    const { default: EpisodeList } = await import(
      "@/components/media/EpisodeList"
    );
    render(
      <EpisodeList
        videos={[]}
        selectedPaths={new Set()}
        onToggleSelect={vi.fn()}
        onPlay={vi.fn()}
        onSearch={vi.fn()}
        onVideoDetail={vi.fn()}
      />
    );
    expect(screen.getByText("暂无视频文件")).toBeInTheDocument();
  });
});

describe("CardGrid 导出", () => {
  it("导出 getSeasonLabel 和 CardItem 类型", async () => {
    const mod = await import("@/components/media/CardGrid");
    expect(mod.getSeasonLabel).toBeTypeOf("function");
    expect(mod.getSeasonLabel("Season 01")).toBe("第1季");
    expect(mod.getSeasonLabel("S03")).toBe("第3季");
    expect(mod.getSeasonLabel("第5季")).toBe("第5季");
    expect(mod.getSeasonLabel("OVA")).toBe("OVA");
  });
});
