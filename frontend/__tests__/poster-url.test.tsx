// 封面 URL 必须按"这一个视频"来取，不能退化成"它所在的目录"。
//
// 用户实际现象：`动画电影` 目录塞了 78 部散装电影，点开任意一部，详情里的封面
// 全都是 VIRGIN PUNK 那张。根因在前端：VideoDetail 把 file_path 正则去掉文件名
// 后当 localPath 传给 Poster，后端拿到目录就走 listdir 取第一个 `*-poster.jpg`。
import { fireEvent, render, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { Poster } from "@/components/detail/DetailComponents";

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    getLocalPoster: vi.fn((p: string, cover?: boolean) =>
      `/backend/scrape/poster?path=${encodeURIComponent(p)}${cover ? "&cover=true" : ""}`),
    getProxiedImage: vi.fn((u: string) => `/backend/proxy/image?url=${encodeURIComponent(u)}`),
    readScrape: vi.fn(async () => ({ status: "not_found" })),
  },
}));
vi.mock("@/lib/api", () => ({ api: mockApi }));

const DIR = "\\\\niuniuos\\video\\动画电影";
const VIDEO_A = `${DIR}\\你好世界 helloworld (2019).mkv`;
const VIDEO_B = `${DIR}\\[SweetSub] VIRGIN PUNK - 01 Clockwork Girl.mkv`;

// img 带 alt=""（装饰性图片），语义角色是 presentation，取不到 role="img"
function posterImg(container: HTMLElement): HTMLImageElement {
  const img = container.querySelector("img");
  if (!img) throw new Error("没有渲染出封面 img");
  return img as HTMLImageElement;
}

function posterSrc(container: HTMLElement): string {
  return posterImg(container).getAttribute("src") || "";
}

beforeEach(() => {
  mockApi.getLocalPoster.mockClear();
  mockApi.readScrape.mockClear();
});

describe("Poster 的 localPath", () => {
  it("视频路径原样进 URL，不被截成目录", () => {
    const { container } = render(<Poster fallbackName="你好世界" localPath={VIDEO_A} aspect="poster" />);
    const src = posterSrc(container);
    expect(src).toContain(encodeURIComponent(VIDEO_A));
    expect(mockApi.getLocalPoster).toHaveBeenCalledWith(VIDEO_A, false);
  });

  it("同目录两部电影拿到不同的封面地址", () => {
    const first = render(<Poster fallbackName="你好世界" localPath={VIDEO_A} aspect="poster" />);
    const a = posterSrc(first.container);
    first.unmount();
    const second = render(<Poster fallbackName="VIRGIN PUNK" localPath={VIDEO_B} aspect="poster" />);
    const b = posterSrc(second.container);
    expect(a).not.toEqual(b);
  });

  it("封面地址里不出现只到目录为止的路径", () => {
    const { container } = render(<Poster fallbackName="你好世界" localPath={VIDEO_A} aspect="poster" />);
    const path = decodeURIComponent(posterSrc(container).split("path=")[1].split("&")[0]);
    expect(path).not.toEqual(DIR);
    expect(path.endsWith(".mkv")).toBe(true);
  });

  it("目录路径（文件夹详情）仍按目录取", () => {
    render(<Poster fallbackName="动画电影" localPath={DIR} />);
    expect(mockApi.getLocalPoster).toHaveBeenCalledWith(DIR, false);
  });

  it("localPath 为空时不请求本地封面", () => {
    render(<Poster fallbackName="无路径" />);
    expect(mockApi.getLocalPoster).not.toHaveBeenCalled();
  });

  it("本地封面缺失时按视频路径去读刮削信息，而不是目录", async () => {
    const { container } = render(<Poster fallbackName="你好世界" localPath={VIDEO_A} aspect="poster" />);
    fireEvent.error(posterImg(container));
    await waitFor(() => expect(mockApi.readScrape).toHaveBeenCalledWith(VIDEO_A, true));
  });
});
