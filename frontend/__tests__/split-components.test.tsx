// 前端拆分组件全面回归测试 — 用真实场景数据验证
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import type { PanResult, VideoInfo, FolderNode } from "@/types";
import type { PanFilterState } from "@/components/search/PanFilterBar";

// ── 测试数据工厂 ──

function makePanResult(overrides: Partial<PanResult> = {}): PanResult {
  return {
    title: "[夸克网盘]流浪地球2.2023.2160p.WEB-DL.H265.DDP5.1",
    clean_title: "流浪地球2 2023 2160p",
    pan_type: "quark",
    share_url: "https://pan.quark.cn/s/abc123",
    password: "",
    source: "pansearch",
    mounted: false,
    resolution: "2160p",
    size_gb: 15.2,
    is_complete: true,
    file_count: 1,
    alive: true,
    ...overrides,
  };
}

function makeVideo(overrides: Partial<VideoInfo> = {}): VideoInfo {
  return {
    file_name: "切尔诺贝利 S01E01.mkv",
    file_path: "\\\\NAS\\视频\\电视剧\\切尔诺贝利\\Season 01\\切尔诺贝利 S01E01.mkv",
    folder_name: "Season 01",
    size_gb: 3.2,
    resolution: "1080p",
    width: 1920, height: 1080,
    duration: 62, audio_codec: "DTS-HD MA",
    video_codec: "x265", subtitle_count: 2,
    hdr_type: "", is_low_res: false,
    shadow_name: "切尔诺贝利 Chernobyl S01E01",
    organize_status: "ok",
    ...overrides,
  };
}

// ══════════════════════════════════════════
// PanFilterBar — 筛选逻辑 + 渲染
// ══════════════════════════════════════════

describe("PanFilterBar 筛选逻辑", () => {
  it("默认筛选器不过滤任何结果", async () => {
    const { applyPanFilters, DEFAULT_PAN_FILTERS } = await import("@/components/search/PanFilterBar");
    const results = [
      makePanResult({ pan_type: "quark", resolution: "2160p", is_complete: true }),
      makePanResult({ pan_type: "aliyun", resolution: "1080p", is_complete: false }),
      makePanResult({ pan_type: "baidu", resolution: "720p", is_complete: true }),
    ];
    expect(applyPanFilters(results, DEFAULT_PAN_FILTERS)).toHaveLength(3);
  });

  it("按网盘类型筛选 — 夸克", async () => {
    const { applyPanFilters } = await import("@/components/search/PanFilterBar");
    const results = [
      makePanResult({ pan_type: "quark" }),
      makePanResult({ pan_type: "aliyun" }),
      makePanResult({ pan_type: "quark" }),
      makePanResult({ pan_type: "pan115" }),
    ];
    const filtered = applyPanFilters(results, { panType: ["quark"], resolution: [], chineseSubOnly: false, completeOnly: false });
    expect(filtered).toHaveLength(2);
    filtered.forEach(r => expect(r.pan_type).toBe("quark"));
  });

  it("按来源筛选 — pansearch", async () => {
    const { applyPanFilters } = await import("@/components/search/PanFilterBar");
    const results = [
      makePanResult({ source: "pansearch" }),
      makePanResult({ source: "pansou" }),
      makePanResult({ source: "github" }),
    ];
    // 新接口：通过 disabledSources 排除不需要的源
    const disabledSources = new Set(["pansou", "github"]);
    const filtered = applyPanFilters(results, { panType: [], resolution: [], chineseSubOnly: false, completeOnly: false }, disabledSources);
    expect(filtered).toHaveLength(1);
    expect(filtered[0].source).toBe("pansearch");
  });

  it("按分辨率筛选 — 4K", async () => {
    const { applyPanFilters } = await import("@/components/search/PanFilterBar");
    const results = [
      makePanResult({ resolution: "2160p" }),
      makePanResult({ resolution: "1080p" }),
      makePanResult({ resolution: "2160p" }),
    ];
    const filtered = applyPanFilters(results, { panType: [], resolution: ["2160p"], chineseSubOnly: false, completeOnly: false });
    expect(filtered).toHaveLength(2);
  });

  it("仅整季筛选 — 排除碎片", async () => {
    const { applyPanFilters } = await import("@/components/search/PanFilterBar");
    const results = [
      makePanResult({ is_complete: true, title: "整季包" }),
      makePanResult({ is_complete: false, title: "单集碎片" }),
      makePanResult({ is_complete: true, title: "另一个整季" }),
    ];
    const filtered = applyPanFilters(results, { panType: [], resolution: [], chineseSubOnly: false, completeOnly: true });
    expect(filtered).toHaveLength(2);
    filtered.forEach(r => expect(r.is_complete).toBe(true));
  });

  it("组合筛选 — 夸克 + 4K + 整季", async () => {
    const { applyPanFilters } = await import("@/components/search/PanFilterBar");
    const results = [
      makePanResult({ pan_type: "quark", resolution: "2160p", is_complete: true }),
      makePanResult({ pan_type: "quark", resolution: "1080p", is_complete: true }),
      makePanResult({ pan_type: "aliyun", resolution: "2160p", is_complete: true }),
      makePanResult({ pan_type: "quark", resolution: "2160p", is_complete: false }),
    ];
    const filtered = applyPanFilters(results, { panType: ["quark"], resolution: ["2160p"], chineseSubOnly: false, completeOnly: true });
    expect(filtered).toHaveLength(1);
    expect(filtered[0].pan_type).toBe("quark");
    expect(filtered[0].resolution).toBe("2160p");
    expect(filtered[0].is_complete).toBe(true);
  });

  it("常量导出完整性", async () => {
    const mod = await import("@/components/search/PanFilterBar");
    expect(mod.PAN_TYPE_COLORS.quark).toBeDefined();
    expect(mod.PAN_TYPE_COLORS.aliyun).toBeDefined();
    expect(mod.PAN_TYPE_COLORS.baidu).toBeDefined();
    expect(mod.PAN_TYPE_COLORS.pan115).toBeDefined();
    expect(mod.PAN_TYPE_COLORS.pikpak).toBeDefined();
    expect(mod.PAN_TYPE_LABELS.quark).toBe("夸克");
    expect(mod.PAN_TYPE_LABELS.aliyun).toBe("阿里");
    expect(mod.SOURCE_LABELS.pansearch).toBe("PanSearch");
    expect(mod.SOURCE_LABELS.github).toBe("GitHub仓库");
  });

  it("渲染筛选栏 — 显示 MultiSelect 下拉按钮", async () => {
    const { default: PanFilterBar, DEFAULT_PAN_FILTERS } = await import("@/components/search/PanFilterBar");
    render(
      <PanFilterBar
        activeSource="all"
        filters={DEFAULT_PAN_FILTERS}
        onChange={vi.fn()}
        groups={{ quark: [makePanResult()], aliyun: [makePanResult({ pan_type: "aliyun" })] }}
        sourceStatuses={[
          { name: "pansearch", status: "success", count: 5, error: "" },
          { name: "pansou", status: "failed", count: 0, error: "timeout" },
        ]}
        panSources={[
          { name: "pansearch", label: "PanSearch", enabled: true },
          { name: "pansou", label: "PanSou", enabled: true },
        ]}
        disabledSources={new Set()}
        onToggleSource={vi.fn()}
      />
    );
    expect(screen.getByText("网盘")).toBeInTheDocument();
    expect(screen.getByText("分辨率")).toBeInTheDocument();
    expect(screen.getByText("特征")).toBeInTheDocument();
  });

  it("清除按钮在有筛选时显示", async () => {
    const { default: PanFilterBar } = await import("@/components/search/PanFilterBar");
    const onChange = vi.fn();
    render(
      <PanFilterBar
        activeSource="all"
        filters={{ panType: ["quark"], resolution: [], chineseSubOnly: false, completeOnly: false }}
        onChange={onChange}
        groups={{ quark: [makePanResult()] }}
        sourceStatuses={[]}
        panSources={[]}
        disabledSources={new Set()}
        onToggleSource={vi.fn()}
      />
    );
    const clearBtn = screen.getByText("清除");
    expect(clearBtn).toBeInTheDocument();
    fireEvent.click(clearBtn);
    expect(onChange).toHaveBeenCalledWith({ panType: [], resolution: [], chineseSubOnly: false, completeOnly: false });
  });
});

// ══════════════════════════════════════════
// PanResultsView — 各状态渲染
// ══════════════════════════════════════════

describe("PanResultsView 场景测试", () => {
  const defaultFilters: PanFilterState = { panType: [], resolution: [], chineseSubOnly: false, completeOnly: false };

  it("搜索中 — 显示 loading 动画", async () => {
    const { default: PanResultsView } = await import("@/components/search/PanResultsView");
    render(<PanResultsView searching={true} groups={{}} total={0} sourceStatuses={[]} keyword="流浪地球" filters={defaultFilters} onRetry={vi.fn()} onTransfer={vi.fn()} />);
    expect(screen.getByText("搜索网盘资源...")).toBeInTheDocument();
  });

  it("无结果 — 显示重试按钮并可点击", async () => {
    const { default: PanResultsView } = await import("@/components/search/PanResultsView");
    const onRetry = vi.fn();
    render(<PanResultsView searching={false} groups={{}} total={0} sourceStatuses={[]} keyword="不存在的电影" filters={defaultFilters} onRetry={onRetry} onTransfer={vi.fn()} />);
    expect(screen.getByText("未搜到网盘资源")).toBeInTheDocument();
    fireEvent.click(screen.getByText("重试"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("有结果 — 按网盘类型分组显示", async () => {
    const { default: PanResultsView } = await import("@/components/search/PanResultsView");
    const groups = {
      quark: [
        makePanResult({ title: "夸克资源1", pan_type: "quark" }),
        makePanResult({ title: "夸克资源2", pan_type: "quark" }),
      ],
      aliyun: [
        makePanResult({ title: "阿里资源1", pan_type: "aliyun" }),
      ],
    };
    render(<PanResultsView searching={false} groups={groups} total={3} sourceStatuses={[]} keyword="test" filters={defaultFilters} onRetry={vi.fn()} onTransfer={vi.fn()} />);
    expect(screen.getAllByText("夸克").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("阿里").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("共 3 条")).toBeInTheDocument();
  });

  it("筛选后无匹配 — 显示提示", async () => {
    const { default: PanResultsView } = await import("@/components/search/PanResultsView");
    const groups = { quark: [makePanResult({ resolution: "1080p" })] };
    render(<PanResultsView searching={false} groups={groups} total={1} sourceStatuses={[]} keyword="test"
      filters={{ panType: [], resolution: ["2160p"], chineseSubOnly: false, completeOnly: false }}
      onRetry={vi.fn()} onTransfer={vi.fn()} />);
    expect(screen.getByText("当前筛选条件无匹配结果")).toBeInTheDocument();
  });

  it("夸克资源显示转存按钮", async () => {
    const { default: PanResultsView } = await import("@/components/search/PanResultsView");
    const onTransfer = vi.fn();
    const groups = { quark: [makePanResult({ pan_type: "quark", title: "流浪地球2.4K" })] };
    render(<PanResultsView searching={false} groups={groups} total={1} sourceStatuses={[]} keyword="test" filters={defaultFilters} onRetry={vi.fn()} onTransfer={onTransfer} />);
    const transferBtn = screen.getByText("转存");
    expect(transferBtn).toBeInTheDocument();
  });

  it("非夸克资源显示打开按钮", async () => {
    const { default: PanResultsView } = await import("@/components/search/PanResultsView");
    const groups = { aliyun: [makePanResult({ pan_type: "aliyun", title: "阿里云盘资源" })] };
    render(<PanResultsView searching={false} groups={groups} total={1} sourceStatuses={[]} keyword="test" filters={defaultFilters} onRetry={vi.fn()} onTransfer={vi.fn()} />);
    expect(screen.getByText("打开")).toBeInTheDocument();
  });

  it("碎片资源显示碎片标签", async () => {
    const { default: PanResultsView } = await import("@/components/search/PanResultsView");
    const groups = { quark: [makePanResult({ is_complete: false })] };
    render(<PanResultsView searching={false} groups={groups} total={1} sourceStatuses={[]} keyword="test" filters={defaultFilters} onRetry={vi.fn()} onTransfer={vi.fn()} />);
    expect(screen.getByText("碎片")).toBeInTheDocument();
  });

  it("有提取码的资源显示密码", async () => {
    const { default: PanResultsView } = await import("@/components/search/PanResultsView");
    const groups = { baidu: [makePanResult({ pan_type: "baidu", password: "ab12" })] };
    render(<PanResultsView searching={false} groups={groups} total={1} sourceStatuses={[]} keyword="test" filters={defaultFilters} onRetry={vi.fn()} onTransfer={vi.fn()} />);
    expect(screen.getByText(/码: ab12/)).toBeInTheDocument();
  });
});

// ══════════════════════════════════════════
// EpisodeTable — 剧集搜索汇总
// ══════════════════════════════════════════

describe("EpisodeTable 场景测试", () => {
  const makeQuality = (display: string) => ({
    resolution: "1080p", source: "WEB-DL", video_codec: "x265",
    audio_codec: "AAC", has_chinese_sub: true, release_group: "GRP",
    is_surround: false, display,
  });

  it("完整剧集 — 全部找到", async () => {
    const { default: EpisodeTable } = await import("@/components/search/EpisodeTable");
    const episodeResults: Record<number, any> = {};
    for (let i = 1; i <= 5; i++) {
      episodeResults[i] = {
        episode: i, status: "found",
        recommended: {
          title: `切尔诺贝利 S01E${String(i).padStart(2, "0")}`, size_gb: 3.2,
          indexer: "Nyaa", seeders: 15, leechers: 3,
          download_url: `magnet:?xt=ep${i}`, quality_tag: "1080p WEB-DL",
          quality: makeQuality("1080p WEB-DL x265"), quality_rank: 5,
        },
        alternatives: [],
      };
    }
    render(
      <EpisodeTable episodeResults={episodeResults} seasonPacks={[]}
        totalSizePack={0} totalSizeEpisode={16} recommendedPlan="per_episode"
        onSelectAlternative={vi.fn()} />
    );
    for (let i = 1; i <= 5; i++) {
      expect(screen.getByText(`E${String(i).padStart(2, "0")}`)).toBeInTheDocument();
    }
    expect(screen.queryByText("⚠ 缺失")).not.toBeInTheDocument();
  });

  it("部分缺失 — 显示缺失标记", async () => {
    const { default: EpisodeTable } = await import("@/components/search/EpisodeTable");
    const episodeResults: Record<number, any> = {
      1: { episode: 1, status: "found", recommended: { title: "EP01", size_gb: 1, indexer: "t", seeders: 5, leechers: 1, download_url: "m", quality_tag: "1080p", quality: makeQuality("1080p"), quality_rank: 5 }, alternatives: [] },
      2: { episode: 2, status: "not_found", recommended: null, alternatives: [] },
      3: { episode: 3, status: "not_found", recommended: null, alternatives: [] },
    };
    render(
      <EpisodeTable episodeResults={episodeResults} seasonPacks={[]}
        totalSizePack={0} totalSizeEpisode={1} recommendedPlan="per_episode"
        onSelectAlternative={vi.fn()} />
    );
    const missing = screen.getAllByText("⚠ 缺失");
    expect(missing).toHaveLength(2);
  });

  it("整季包 vs 逐集 — 方案对比面板", async () => {
    const { default: EpisodeTable } = await import("@/components/search/EpisodeTable");
    const episodeResults: Record<number, any> = {
      1: { episode: 1, status: "found", recommended: { title: "EP01", size_gb: 3, indexer: "t", seeders: 10, leechers: 1, download_url: "m", quality_tag: "1080p", quality: makeQuality("1080p"), quality_rank: 5 }, alternatives: [] },
    };
    const seasonPacks = [{
      result: { title: "Pack", size_gb: 25, indexer: "t", seeders: 20, leechers: 5, download_url: "m", quality_tag: "1080p", quality: makeQuality("1080p Bluray"), quality_rank: 7 },
      verification: { verified: true, is_magnet: true, episode_count: 10, episodes_found: [1,2,3,4,5,6,7,8,9,10], is_complete: true },
    }];
    render(
      <EpisodeTable episodeResults={episodeResults} seasonPacks={seasonPacks}
        totalSizePack={25} totalSizeEpisode={3} recommendedPlan="season_pack"
        onSelectAlternative={vi.fn()} />
    );
    expect(screen.getByText("整季包方案")).toBeInTheDocument();
    expect(screen.getByText("逐集拼凑方案")).toBeInTheDocument();
    expect(screen.getByText("25 GB")).toBeInTheDocument();
    expect(screen.getAllByText("3 GB").length).toBeGreaterThanOrEqual(1);
  });

  it("有备选 — 点击展开备选列表", async () => {
    const { default: EpisodeTable } = await import("@/components/search/EpisodeTable");
    const onSelect = vi.fn();
    const alt = { title: "备选资源", size_gb: 2.5, indexer: "t", seeders: 8, leechers: 2, download_url: "alt", quality_tag: "720p", quality: makeQuality("720p WEB-DL"), quality_rank: 3 };
    const episodeResults: Record<number, any> = {
      1: {
        episode: 1, status: "found",
        recommended: { title: "推荐", size_gb: 3, indexer: "t", seeders: 10, leechers: 1, download_url: "m", quality_tag: "1080p", quality: makeQuality("1080p"), quality_rank: 5 },
        alternatives: [alt],
      },
    };
    render(<EpisodeTable episodeResults={episodeResults} seasonPacks={[]} totalSizePack={0} totalSizeEpisode={3} recommendedPlan="per_episode" onSelectAlternative={onSelect} />);
    fireEvent.click(screen.getByText("1个备选"));
    expect(screen.getByText("选择")).toBeInTheDocument();
    fireEvent.click(screen.getByText("选择"));
    expect(onSelect).toHaveBeenCalledWith(1, alt);
  });
});

// ══════════════════════════════════════════
// CardPoster — 封面组件
// ══════════════════════════════════════════

describe("CardPoster 场景测试", () => {
  it("无 path — 显示占位图标", async () => {
    const { default: CardPoster } = await import("@/components/media/CardPoster");
    render(<CardPoster name="流浪地球2" />);
    expect(screen.getByText("🎬")).toBeInTheDocument();
  });

  it("有 path — 生成正确的本地海报 URL", async () => {
    const { default: CardPoster } = await import("@/components/media/CardPoster");
    const { container } = render(<CardPoster name="切尔诺贝利" path="/nas/video/chernobyl" />);
    const img = container.querySelector("img");
    expect(img).toBeTruthy();
    expect(img?.src).toContain("/scrape/poster?path=");
    expect(img?.src).toContain("%2Fnas%2Fvideo%2Fchernobyl");
  });

  it("cover 模式 — URL 包含 cover=true", async () => {
    const { default: CardPoster } = await import("@/components/media/CardPoster");
    const { container } = render(<CardPoster name="系列合集" path="/test/collection" cover={true} />);
    const img = container.querySelector("img");
    expect(img?.src).toContain("cover=true");
  });

  it("cacheKey 变化 — URL 包含缓存破坏参数", async () => {
    const { default: CardPoster } = await import("@/components/media/CardPoster");
    const { container } = render(<CardPoster name="test" path="/test" cacheKey={12345} />);
    const img = container.querySelector("img");
    expect(img?.src).toContain("_t=12345");
  });
});

// ══════════════════════════════════════════
// EpisodeList — 剧集列表
// ══════════════════════════════════════════

describe("EpisodeList 场景测试", () => {
  it("渲染切尔诺贝利 5 集", async () => {
    const { default: EpisodeList } = await import("@/components/media/EpisodeList");
    const videos = Array.from({ length: 5 }, (_, i) => makeVideo({
      file_name: `切尔诺贝利 Chernobyl S01E${String(i + 1).padStart(2, "0")}.mkv`,
      file_path: `/nas/切尔诺贝利/S01E${String(i + 1).padStart(2, "0")}.mkv`,
      size_gb: 3.0 + i * 0.1,
    }));
    render(
      <EpisodeList videos={videos} selectedPaths={new Set()} onToggleSelect={vi.fn()}
        onPlay={vi.fn()} onSearch={vi.fn()} onVideoDetail={vi.fn()} />
    );
    for (let i = 1; i <= 5; i++) {
      expect(screen.getByText(new RegExp(`S01E${String(i).padStart(2, "0")}`))).toBeInTheDocument();
    }
    expect(screen.getAllByText("1080p")).toHaveLength(5);
  });

  it("空列表 — 显示暂无视频文件", async () => {
    const { default: EpisodeList } = await import("@/components/media/EpisodeList");
    render(
      <EpisodeList videos={[]} selectedPaths={new Set()} onToggleSelect={vi.fn()}
        onPlay={vi.fn()} onSearch={vi.fn()} onVideoDetail={vi.fn()} />
    );
    expect(screen.getByText("暂无视频文件")).toBeInTheDocument();
  });

  it("批量模式 — 显示复选框", async () => {
    const { default: EpisodeList } = await import("@/components/media/EpisodeList");
    const videos = [makeVideo()];
    const { container } = render(
      <EpisodeList videos={videos} selectedPaths={new Set()} onToggleSelect={vi.fn()}
        onPlay={vi.fn()} onSearch={vi.fn()} onVideoDetail={vi.fn()} batchMode={true} />
    );
    const checkboxes = container.querySelectorAll('input[type="checkbox"]');
    expect(checkboxes).toHaveLength(1);
  });

  it("已选中的视频 — 高亮显示", async () => {
    const { default: EpisodeList } = await import("@/components/media/EpisodeList");
    const video = makeVideo({ file_path: "/selected/video.mkv" });
    const { container } = render(
      <EpisodeList videos={[video]} selectedPaths={new Set(["/selected/video.mkv"])}
        onToggleSelect={vi.fn()} onPlay={vi.fn()} onSearch={vi.fn()} onVideoDetail={vi.fn()} batchMode={true} />
    );
    const checkbox = container.querySelector('input[type="checkbox"]') as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
  });

  it("未整理视频 — 显示灰色圆点", async () => {
    const { default: EpisodeList } = await import("@/components/media/EpisodeList");
    const video = makeVideo({ shadow_name: undefined, organize_status: undefined });
    const { container } = render(
      <EpisodeList videos={[video]} selectedPaths={new Set()} onToggleSelect={vi.fn()}
        onPlay={vi.fn()} onSearch={vi.fn()} onVideoDetail={vi.fn()} />
    );
    const dot = container.querySelector('[title="未整理"]');
    expect(dot).toBeTruthy();
  });

  it("刮削失败视频 — 显示警告图标", async () => {
    const { default: EpisodeList } = await import("@/components/media/EpisodeList");
    const video = makeVideo({ organize_status: "scrape_failed" });
    const { container } = render(
      <EpisodeList videos={[video]} selectedPaths={new Set()} onToggleSelect={vi.fn()}
        onPlay={vi.fn()} onSearch={vi.fn()} onVideoDetail={vi.fn()} />
    );
    const warn = container.querySelector('[title="识别失败"]');
    expect(warn).toBeTruthy();
  });

  it("点击视频行 — 触发 onVideoDetail", async () => {
    const { default: EpisodeList } = await import("@/components/media/EpisodeList");
    const onVideoDetail = vi.fn();
    const video = makeVideo();
    render(
      <EpisodeList videos={[video]} selectedPaths={new Set()} onToggleSelect={vi.fn()}
        onPlay={vi.fn()} onSearch={vi.fn()} onVideoDetail={onVideoDetail} />
    );
    fireEvent.click(screen.getByText(video.file_name));
    expect(onVideoDetail).toHaveBeenCalledWith(video);
  });
});

// ══════════════════════════════════════════
// CardGrid 导出兼容性
// ══════════════════════════════════════════

describe("CardGrid 导出兼容性", () => {
  it("getSeasonLabel — 各种季号格式", async () => {
    const { getSeasonLabel } = await import("@/components/media/CardGrid");
    expect(getSeasonLabel("Season 01")).toBe("第1季");
    expect(getSeasonLabel("Season 12")).toBe("第12季");
    expect(getSeasonLabel("S03")).toBe("第3季");
    expect(getSeasonLabel("第5季")).toBe("第5季");
    expect(getSeasonLabel("OVA")).toBe("OVA");
    expect(getSeasonLabel("特别篇")).toBe("特别篇");
    expect(getSeasonLabel("Specials")).toBe("Specials");
  });

  it("CardItem 类型可导入", async () => {
    // 验证 CardItem 类型导出存在（编译时检查）
    const mod = await import("@/components/media/CardGrid");
    expect(mod.getSeasonLabel).toBeTypeOf("function");
    // CardItem 是 type，运行时不存在，但 getSeasonLabel 的存在证明模块导出正常
  });
});
