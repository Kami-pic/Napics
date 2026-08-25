// 移动端原生播放页：URL 构造、字幕过滤、可播性判定、插件缺失与播放失败提示。
//
// jsdom 实情：`canPlayType` 存在但**恒返回空串**，所以"可播"的正分支必须 stub 它；
// 不 stub 就等于永远走"格式不支持"分支。
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import MobileNativePlayer, { pickExternalSubtitles } from "@/components/mobile/MobileNativePlayer";
import { buildStreamUrl, resolveSubtitleUrl } from "@/lib/domain/playback";

const { mockPlugins } = vi.hoisted(() => ({
  mockPlugins: { value: { hasPlayer: true, ready: true } },
}));
vi.mock("@/components/mobile/MobileProviders", () => ({
  useMobilePlugins: () => mockPlugins.value,
}));

const MP4 = "D:\\影视\\电影\\钢铁侠 Iron Man (2008)\\钢铁侠 Iron Man (2008).mp4";
const MKV = "D:\\影视\\剧集\\三体 (2023)\\Season 1\\三体 S01E01.mkv";
const SUB_PATH = "D:\\影视\\电影\\钢铁侠 Iron Man (2008)\\钢铁侠 Iron Man (2008).chs.srt";

/** 后端返回的形状：url 里的路径已经 quote 过一次 */
function subtitleResponse() {
  return {
    subtitles: [
      {
        name: "钢铁侠.chs.srt",
        lang: "zh",
        url: `/playback/subtitle/file?path=${encodeURIComponent(SUB_PATH)}`,
        embedded: false,
        unsupported: false,
        kind: "external",
      },
      {
        name: "英文内嵌",
        lang: "en",
        url: "/playback/subtitle/extract?path=x&index=3",
        embedded: true,
        unsupported: false,
        kind: "embedded",
      },
      {
        name: "PGS 图形字幕",
        lang: "zh",
        url: "/playback/subtitle/extract?path=x&index=4",
        embedded: true,
        unsupported: true,
        kind: "graphic",
      },
    ],
    summary: { external: 1, embedded: 1, graphic: 1, maybe_hardcoded: false },
  };
}

let canPlaySpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  mockPlugins.value = { hasPlayer: true, ready: true };
  // 默认 stub 成"能播"，测不可播的用例里单独改
  canPlaySpy = vi.spyOn(HTMLMediaElement.prototype, "canPlayType").mockReturnValue("maybe");
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(subtitleResponse()), {
    headers: { "content-type": "application/json" },
  })));
});

afterEach(() => {
  canPlaySpy.mockRestore();
  vi.unstubAllGlobals();
});

async function mount(path: string) {
  render(<MobileNativePlayer path={path} />);
  await act(async () => { await Promise.resolve(); });
}

describe("字幕过滤（纯函数）", () => {
  it("只留外挂且可渲染的：内嵌要全量 demux，图形字幕是图片", () => {
    const picked = pickExternalSubtitles(subtitleResponse().subtitles);
    expect(picked.length).toBe(1);
    expect(picked[0].name).toBe("钢铁侠.chs.srt");
    expect(picked[0].url).toBe(resolveSubtitleUrl(subtitleResponse().subtitles[0].url));
  });

  it("没有 url 的条目丢掉，不产出空 src 的 track", () => {
    expect(pickExternalSubtitles([{ name: "坏数据", embedded: false, unsupported: false }])).toEqual([]);
  });

  it("空输入不炸", () => {
    expect(pickExternalSubtitles([])).toEqual([]);
  });
});

describe("播放器渲染", () => {
  it("src 走共享 helper，且 path 只编码一次", async () => {
    await mount(MP4);
    const video = screen.getByTestId("mobile-video");
    expect(video.getAttribute("src")).toBe(buildStreamUrl(MP4));
    expect(new URL(video.getAttribute("src")!, "http://x").searchParams.get("path")).toBe(MP4);
  });

  it("controls + playsInline + preload=metadata（iOS 内联播放的三个前提）", async () => {
    await mount(MP4);
    const video = screen.getByTestId("mobile-video") as HTMLVideoElement;
    expect(video.controls).toBe(true);
    expect(video.getAttribute("playsinline")).not.toBeNull();
    expect(video.getAttribute("preload")).toBe("metadata");
  });

  it("不自动播放：没有 autoplay 属性，也不调 play()", async () => {
    const playSpy = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    await mount(MP4);
    expect(screen.getByTestId("mobile-video").getAttribute("autoplay")).toBeNull();
    expect(playSpy).not.toHaveBeenCalled();
    playSpy.mockRestore();
  });

  it("外挂字幕挂成 track，URL 不被二次编码", async () => {
    await mount(MP4);
    await waitFor(() => expect(document.querySelectorAll("track").length).toBe(1));
    const track = document.querySelector("track")!;
    expect(track.getAttribute("src")).toContain("/playback/subtitle/file");
    expect(track.getAttribute("src")).not.toContain("%25");
    expect(track.getAttribute("srclang")).toBe("zh");
    expect(screen.getByText(/外挂字幕 1 条/)).toBeTruthy();
  });

  it("只有内嵌/图形字幕时说明原因，而不是假装没字幕", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      subtitles: [{ name: "PGS", embedded: true, unsupported: true, url: "/x" }],
      summary: { maybe_hardcoded: false },
    }), { headers: { "content-type": "application/json" } })));
    await mount(MKV);
    await waitFor(() => expect(screen.getByText(/只有内封或图形字幕/)).toBeTruthy());
    expect(document.querySelectorAll("track").length).toBe(0);
  });

  it("字幕列表请求失败不影响播放，只给一行提示", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("boom", { status: 500 })));
    await mount(MP4);
    await waitFor(() => expect(screen.getByText(/字幕列表获取失败/)).toBeTruthy());
    expect(screen.getByTestId("mobile-video")).toBeTruthy();
  });
});

describe("可播性与失败提示", () => {
  it("扩展名不在候选集内 → 提前警告（mkv 不能原生播）", async () => {
    await mount(MKV);
    expect(screen.getByText(/浏览器可能无法播放这个格式/)).toBeTruthy();
    expect(screen.getByText(/mkv/)).toBeTruthy();
  });

  it("候选集内但 canPlayType 说不行 → 同样警告", async () => {
    canPlaySpy.mockReturnValue("");
    await mount(MP4);
    expect(screen.getByText(/浏览器可能无法播放这个格式/)).toBeTruthy();
  });

  it("能播时不显示任何格式警告", async () => {
    await mount(MP4);
    expect(screen.queryByText(/浏览器可能无法播放/)).toBeNull();
  });

  it("media error 事件 → 明确说是编码不支持，不是空白", async () => {
    await mount(MP4);
    fireEvent.error(screen.getByTestId("mobile-video"));
    expect(screen.getByRole("alert").textContent).toMatch(/编码不受浏览器支持/);
  });
});

describe("前置条件", () => {
  it("没有 path → 明确提示", async () => {
    await mount("");
    expect(screen.getByText("缺少视频路径，无法播放")).toBeTruthy();
    expect(screen.queryByTestId("mobile-video")).toBeNull();
  });

  it("播放插件不可用 → 说清是插件问题，不渲染播放器", async () => {
    mockPlugins.value = { hasPlayer: false, ready: true };
    await mount(MP4);
    expect(screen.getByText(/feature-player/)).toBeTruthy();
    expect(screen.queryByTestId("mobile-video")).toBeNull();
  });

  it("插件状态还没到 → 加载态，不先渲染播放器再撤回", async () => {
    mockPlugins.value = { hasPlayer: false, ready: false };
    await mount(MP4);
    expect(screen.getByText("正在检查播放能力…")).toBeTruthy();
  });

  it("插件不可用时不请求字幕列表", async () => {
    mockPlugins.value = { hasPlayer: false, ready: true };
    await mount(MP4);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
