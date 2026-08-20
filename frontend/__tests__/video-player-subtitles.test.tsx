// 播放器字幕加载：外挂立即可用、内嵌按需提取、状态不能卡在 loading
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { VideoPlayer } from "@/components/media/VideoPlayer";

const VTT = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n测试字幕\n";

function mockSubtitleApi(tracks: any[], contentByUrl: Record<string, string | number> = {}) {
  return vi.fn(async (input: any) => {
    const url = String(input);
    if (url.includes("/playback/subtitles")) {
      return new Response(JSON.stringify({ subtitles: tracks }), { status: 200 });
    }
    if (url.includes("/playback/duration")) {
      return new Response(JSON.stringify({ duration: 1200 }), { status: 200 });
    }
    if (url.includes("/playback/audio-tracks")) {
      return new Response(JSON.stringify({ tracks: [] }), { status: 200 });
    }
    if (url.includes("/playback/keyframe-time")) {
      return new Response(JSON.stringify({ actual_start: 0 }), { status: 200 });
    }
    // 字幕内容
    for (const [key, val] of Object.entries(contentByUrl)) {
      if (url.includes(key)) {
        if (typeof val === "number") return new Response("", { status: val });
        return new Response(val, { status: 200 });
      }
    }
    return new Response("", { status: 404 });
  });
}

const externalSrt = {
  name: "movie.chs.srt",
  format: "srt",
  kind: "external",
  codec: "srt",
  lang: "zh",
  url: "/playback/subtitle/file?path=/v/movie.chs.srt",
  embedded: false,
  unsupported: false,
  unsupported_reason: "",
  forced: false,
};

const externalAss = {
  name: "movie.sc.ass",
  format: "ass",
  kind: "external",
  codec: "ass",
  lang: "zh",
  url: "/playback/subtitle/file?path=/v/movie.sc.ass",
  embedded: false,
  unsupported: false,
  unsupported_reason: "",
  forced: false,
};

const embeddedSub = {
  name: "en 字幕 1",
  format: "embedded",
  kind: "embedded",
  codec: "subrip",
  lang: "en",
  url: "/playback/subtitle/extract?path=/v/a.mkv&index=2",
  embedded: true,
  unsupported: false,
  unsupported_reason: "",
  forced: false,
};

const pgsSub = {
  name: "en 字幕 2",
  format: "embedded",
  kind: "graphic",
  codec: "hdmv_pgs_subtitle",
  lang: "en",
  url: "/playback/subtitle/extract?path=/v/a.mkv&index=3",
  embedded: true,
  unsupported: true,
  unsupported_reason: "图形字幕（需 OCR），浏览器无法渲染",
  forced: false,
};

beforeEach(() => {
  // jsdom 没实现这些
  (window as any).HTMLMediaElement.prototype.load = vi.fn();
  (window as any).HTMLMediaElement.prototype.play = vi.fn(() => Promise.resolve());
  (window as any).HTMLMediaElement.prototype.pause = vi.fn();
  global.URL.createObjectURL = vi.fn(() => "blob:mock");
  global.URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("外挂字幕（mp4 原生播放路径）", () => {
  it("srt 外挂字幕必须真正拉到内容，不能卡在提取中", async () => {
    const fetchMock = mockSubtitleApi([externalSrt], { "subtitle/file": VTT });
    global.fetch = fetchMock as any;

    render(<VideoPlayer path="/v/movie.mp4" onClose={() => {}} />);

    // 必须真的发出了取内容的请求 —— 曾经因为 updater 双调用导致
    // loading 被置 true 但 fetch 从未执行，UI 永远显示"提取中"
    await waitFor(() => {
      const called = fetchMock.mock.calls.some(c => String(c[0]).includes("subtitle/file"));
      expect(called, "应发起外挂字幕内容请求").toBe(true);
    }, { timeout: 3000 });

    // 不应残留"正在提取"提示
    await waitFor(() => {
      expect(screen.queryByText(/正在提取内嵌字幕/)).toBeNull();
    }, { timeout: 3000 });
  });

  it("ass 外挂字幕同样要拉到内容", async () => {
    const fetchMock = mockSubtitleApi([externalAss], { "subtitle/file": VTT });
    global.fetch = fetchMock as any;

    render(<VideoPlayer path="/v/movie.mp4" onClose={() => {}} />);

    await waitFor(() => {
      const called = fetchMock.mock.calls.some(c => String(c[0]).includes("subtitle/file"));
      expect(called).toBe(true);
    }, { timeout: 3000 });
  });

  it("mp4 播放时外挂字幕会注入 track 元素", async () => {
    const fetchMock = mockSubtitleApi([externalSrt], { "subtitle/file": VTT });
    global.fetch = fetchMock as any;

    const { container } = render(<VideoPlayer path="/v/movie.mp4" onClose={() => {}} />);

    await waitFor(() => {
      const tracks = container.querySelectorAll("track");
      expect(tracks.length, "应注入 <track>").toBeGreaterThan(0);
    }, { timeout: 3000 });
  });
});

describe("内嵌字幕（mkv 转码路径）", () => {
  it("默认选中的内嵌字幕应自动发起提取", async () => {
    const fetchMock = mockSubtitleApi([embeddedSub], { "subtitle/extract": VTT });
    global.fetch = fetchMock as any;

    render(<VideoPlayer path="/v/a.mkv" onClose={() => {}} />);

    await waitFor(() => {
      const called = fetchMock.mock.calls.some(c => String(c[0]).includes("subtitle/extract"));
      expect(called, "应发起内嵌字幕提取请求").toBe(true);
    }, { timeout: 3000 });
  });

  it("外挂与内嵌共存时优先选外挂，不触发昂贵的内嵌提取", async () => {
    const fetchMock = mockSubtitleApi([embeddedSub, externalSrt], {
      "subtitle/file": VTT,
      "subtitle/extract": VTT,
    });
    global.fetch = fetchMock as any;

    render(<VideoPlayer path="/v/a.mkv" onClose={() => {}} />);

    await waitFor(() => {
      const fileCalled = fetchMock.mock.calls.some(c => String(c[0]).includes("subtitle/file"));
      expect(fileCalled).toBe(true);
    }, { timeout: 3000 });

    // 内嵌提取要全量 demux，没被选中就不该发起
    const extractCalled = fetchMock.mock.calls.some(c => String(c[0]).includes("subtitle/extract"));
    expect(extractCalled, "未选中的内嵌字幕不应被提取").toBe(false);
  });

  it("图形字幕不应被提取（省掉必然失败的请求）", async () => {
    const fetchMock = mockSubtitleApi([pgsSub], { "subtitle/extract": VTT });
    global.fetch = fetchMock as any;

    render(<VideoPlayer path="/v/a.mkv" onClose={() => {}} />);

    await waitFor(() => {
      const listed = fetchMock.mock.calls.some(c => String(c[0]).includes("/playback/subtitles"));
      expect(listed).toBe(true);
    }, { timeout: 3000 });

    await new Promise(r => setTimeout(r, 200));
    const extractCalled = fetchMock.mock.calls.some(c => String(c[0]).includes("subtitle/extract"));
    expect(extractCalled, "图形字幕不可渲染，不该请求提取").toBe(false);
  });

  it("全部字幕都不可用时给出明确说明", async () => {
    const fetchMock = mockSubtitleApi([pgsSub]);
    global.fetch = fetchMock as any;

    render(<VideoPlayer path="/v/a.mkv" onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/图形字幕|无法渲染|格式不支持/)).toBeTruthy();
    }, { timeout: 3000 });
  });
});

describe("失败处理", () => {
  it("字幕内容请求失败时不能一直显示提取中", async () => {
    const fetchMock = mockSubtitleApi([externalSrt], { "subtitle/file": 500 });
    global.fetch = fetchMock as any;

    render(<VideoPlayer path="/v/movie.mp4" onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/加载失败|提取失败/)).toBeTruthy();
    }, { timeout: 3000 });

    expect(screen.queryByText(/正在提取内嵌字幕/)).toBeNull();
  });
});


describe("字幕类型区分", () => {
  it("一条字幕流都没有时提示可能是硬字幕", async () => {
    const fetchMock = vi.fn(async (input: any) => {
      const url = String(input);
      if (url.includes("/playback/subtitles")) {
        return new Response(JSON.stringify({
          subtitles: [],
          summary: { external: 0, embedded: 0, graphic: 0, maybe_hardcoded: true },
        }), { status: 200 });
      }
      if (url.includes("/playback/duration")) {
        return new Response(JSON.stringify({ duration: 100 }), { status: 200 });
      }
      if (url.includes("/playback/audio-tracks")) {
        return new Response(JSON.stringify({ tracks: [] }), { status: 200 });
      }
      return new Response("", { status: 404 });
    });
    global.fetch = fetchMock as any;

    render(<VideoPlayer path="/v/hard.mkv" onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/硬字幕|压制进画面/)).toBeTruthy();
    }, { timeout: 3000 });
  });

  it("图形字幕说明里要点出是图片不是文本", async () => {
    const fetchMock = mockSubtitleApi([pgsSub]);
    global.fetch = fetchMock as any;

    render(<VideoPlayer path="/v/pgs.mkv" onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/图片|PGS|OCR|无法渲染/)).toBeTruthy();
    }, { timeout: 3000 });
  });

  it("外挂与内嵌混合时两类都列出且可区分", async () => {
    const fetchMock = mockSubtitleApi(
      [{ ...externalSrt, kind: "external" }, { ...embeddedSub, kind: "embedded" }, { ...pgsSub, kind: "graphic" }],
      { "subtitle/file": VTT, "subtitle/extract": VTT },
    );
    global.fetch = fetchMock as any;

    render(<VideoPlayer path="/v/mix.mkv" onClose={() => {}} />);

    // 等外挂字幕加载完（优先级最高会被默认选中）
    await waitFor(() => {
      const called = fetchMock.mock.calls.some(c => String(c[0]).includes("subtitle/file"));
      expect(called).toBe(true);
    }, { timeout: 3000 });

    // 打开字幕菜单应能看到三类标签
    const subBtn = document.querySelector('button[title="字幕"]');
    if (subBtn) {
      await act(async () => { (subBtn as HTMLElement).click(); });
      await waitFor(() => {
        expect(screen.getByText("外挂")).toBeTruthy();
        expect(screen.getByText("内嵌")).toBeTruthy();
        expect(screen.getByText("图形")).toBeTruthy();
      }, { timeout: 2000 });
    }
  });
});
