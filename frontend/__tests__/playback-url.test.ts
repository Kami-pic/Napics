// 播放域 URL 构造与原生可播判定。
//
// 核心断言是**编码只发生一次**：后端返回的字幕 url 已经 quote 过，
// 再编码一遍会把 % 变成 %25，后端 unquote 后拿到带字面 %20 的路径 → 文件不存在。
import { describe, it, expect } from "vitest";
import { BASE_URL } from "@/lib/api/base";
import {
  NATIVE_VIDEO_EXTENSION_CANDIDATES,
  videoExtension,
  isNativeExtensionCandidate,
  canPlayNatively,
  buildStreamUrl,
  buildSubtitleListUrl,
  resolveSubtitleUrl,
} from "@/lib/domain/playback";
import { api } from "@/lib/api";

const WIN_PATH = "D:\\影视\\钢铁侠 Iron Man (2008)\\钢铁侠 Iron Man (2008).mp4";
const UNC_PATH = "\\\\NAS\\share\\视频\\剧集 S01E01.mkv";

describe("字幕 URL 只编码一次", () => {
  it("后端已 quote 的 url 往返 decode 得到原路径", () => {
    // 后端就是这么拼的：f"/playback/subtitle/file?path={quote(full_path)}"
    const backendUrl = `/playback/subtitle/file?path=${encodeURIComponent(WIN_PATH)}`;
    const resolved = resolveSubtitleUrl(backendUrl);

    expect(resolved).toBe(`${BASE_URL}${backendUrl}`);
    const roundTripped = decodeURIComponent(new URL(resolved, "http://x").searchParams.get("path")!);
    expect(roundTripped).toBe(WIN_PATH);
    // 双重编码的特征：出现 %25
    expect(resolved).not.toContain("%25");
  });

  it("UNC 路径同样只编码一次", () => {
    const backendUrl = `/playback/subtitle/file?path=${encodeURIComponent(UNC_PATH)}`;
    const resolved = resolveSubtitleUrl(backendUrl);
    const path = new URL(resolved, "http://x").searchParams.get("path")!;
    expect(decodeURIComponent(path)).toBe(UNC_PATH);
  });

  it("绝对地址原样返回，不叠 BASE_URL", () => {
    expect(resolveSubtitleUrl("http://192.168.1.9:8001/playback/subtitle/file?path=a"))
      .toBe("http://192.168.1.9:8001/playback/subtitle/file?path=a");
  });

  it("已带 BASE_URL 前缀的不重复叠加", () => {
    const once = `${BASE_URL}/playback/subtitle/file?path=a`;
    expect(resolveSubtitleUrl(once)).toBe(once);
  });

  it("空 url 返回空串，不产出只有前缀的坏地址", () => {
    expect(resolveSubtitleUrl("")).toBe("");
  });
});

describe("流 URL 自己编码一次", () => {
  it("stream URL 带 BASE_URL，path 往返一致", () => {
    const url = buildStreamUrl(WIN_PATH);
    expect(url.startsWith(`${BASE_URL}/playback/stream?`)).toBe(true);
    expect(new URL(url, "http://x").searchParams.get("path")).toBe(WIN_PATH);
  });

  it("audio_index 为 0 时不带该参数（走原文件，不触发 remux）", () => {
    expect(buildStreamUrl(WIN_PATH)).not.toContain("audio_index");
    expect(new URL(buildStreamUrl(WIN_PATH, 2), "http://x").searchParams.get("audio_index")).toBe("2");
  });

  it("字幕列表 URL 的 path 往返一致", () => {
    const url = buildSubtitleListUrl(UNC_PATH);
    expect(new URL(url, "http://x").searchParams.get("path")).toBe(UNC_PATH);
  });
});

describe("原生可播判定", () => {
  it("扩展名取值大小写无关，UNC 与 Windows 分隔符都能取到", () => {
    expect(videoExtension("D:\\a\\b.MP4")).toBe("mp4");
    expect(videoExtension(UNC_PATH)).toBe("mkv");
    expect(videoExtension("/mnt/media/no-ext")).toBe("");
  });

  it("候选集内外分明", () => {
    for (const ext of NATIVE_VIDEO_EXTENSION_CANDIDATES) {
      expect(isNativeExtensionCandidate(`/a/b.${ext}`)).toBe(true);
    }
    expect(isNativeExtensionCandidate(UNC_PATH)).toBe(false);
    expect(isNativeExtensionCandidate("/a/b.rmvb")).toBe(false);
  });

  it("候选之外的扩展名，即使 canPlayType 说行也判为不可播", () => {
    const video = { canPlayType: () => "probably" } as unknown as HTMLVideoElement;
    expect(canPlayNatively(UNC_PATH, video)).toBe(false);
  });

  it("候选之内但 canPlayType 返回空串则判为不可播（jsdom 默认就是这个值）", () => {
    const video = { canPlayType: () => "" } as unknown as HTMLVideoElement;
    expect(canPlayNatively(WIN_PATH, video)).toBe(false);
  });

  it("stub canPlayType 后走可播正分支", () => {
    const video = { canPlayType: () => "maybe" } as unknown as HTMLVideoElement;
    expect(canPlayNatively(WIN_PATH, video)).toBe(true);
  });

  it("没有 video 元素时只做扩展名初筛", () => {
    expect(canPlayNatively(WIN_PATH, null)).toBe(true);
    expect(canPlayNatively(UNC_PATH, null)).toBe(false);
  });
});

describe("subtitleApi 聚合", () => {
  it("挂成命名空间，没有覆盖 searchApi / downloadApi 的同名方法", () => {
    expect(typeof api.subtitle.search).toBe("function");
    expect(typeof api.subtitle.download).toBe("function");
    // 撞名的两个仍然是各自领域的实现（先确认存在，否则 not.toBe 恒成立）
    expect(typeof api.search).toBe("function");
    expect(typeof api.download).toBe("function");
    expect(api.search).not.toBe(api.subtitle.search);
    expect(api.download).not.toBe(api.subtitle.download);
  });
});
