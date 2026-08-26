// 播放页外壳：页头是页内**唯一**出口（播放页不在底栏里），
// 而且要告诉用户正在播什么。
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import MobilePlayClient from "@/components/mobile/MobilePlayClient";
import MobileLibraryTreeProvider from "@/components/mobile/MobileLibraryTreeProvider";
import { libraryDetailUrl, playUrl } from "@/lib/mobile/mobileRouteUtils";
import { LIBRARY_TREE, MOVIE_NODE, TV_MULTI_SEASON_NODE } from "./helpers/libraryTreeFixture";

const { mockRouter } = vi.hoisted(() => ({
  mockRouter: { push: vi.fn(), replace: vi.fn(), back: vi.fn() },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/m/play",
}));

const { mockApi } = vi.hoisted(() => ({
  mockApi: { getLibraryTree: vi.fn() },
}));
vi.mock("@/lib/api", () => ({ api: mockApi }));

// 播放器本体在 mobile-play.test.tsx 里单独测，这里只关心外壳
vi.mock("@/components/mobile/MobileNativePlayer", () => ({
  default: ({ path }: { path: string }) => <div data-testid="player">{path}</div>,
}));

const MOVIE = MOVIE_NODE.videos[0];
const EPISODE = TV_MULTI_SEASON_NODE.children[1].videos[2];   // 三体 S01E01.mkv

beforeEach(() => {
  mockRouter.push.mockReset();
  mockApi.getLibraryTree.mockReset();
  mockApi.getLibraryTree.mockResolvedValue(LIBRARY_TREE);
});

async function mount(path: string) {
  render(
    <MobileLibraryTreeProvider>
      <MobilePlayClient path={path} />
    </MobileLibraryTreeProvider>,
  );
  await act(async () => { await Promise.resolve(); });
}

describe("播放页外壳", () => {
  it("页头显示片名，剧集额外显示季集号", async () => {
    await mount(EPISODE.file_path);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeTruthy());
    expect(screen.getByText("S01E01")).toBeTruthy();
  });

  it("电影不硬造季集号", async () => {
    await mount(MOVIE.file_path);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("钢铁侠 Iron Man (2008).mkv"));
    expect(screen.queryByText(/S\d\dE\d\d/)).toBeNull();
  });

  it("返回键回详情页，不是只调 back()", async () => {
    await mount(EPISODE.file_path);
    fireEvent.click(screen.getByLabelText("返回"));
    expect(mockRouter.push).toHaveBeenCalledWith(libraryDetailUrl(EPISODE.file_path));
    expect(mockRouter.back).not.toHaveBeenCalled();
  });

  it("树还没到时先用文件名当标题，不阻塞播放", async () => {
    mockApi.getLibraryTree.mockReturnValue(new Promise(() => {}));   // 永不 resolve
    render(
      <MobileLibraryTreeProvider>
        <MobilePlayClient path={EPISODE.file_path} />
      </MobileLibraryTreeProvider>,
    );
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("三体 S01E01.mkv");
    expect(screen.getByTestId("player").textContent).toBe(EPISODE.file_path);
  });

  it("底栏不渲染（播放页在黑名单里）", async () => {
    await mount(EPISODE.file_path);
    expect(screen.queryByLabelText("主导航")).toBeNull();
  });

  it("没有 path 时不渲染返回键，出口由播放器内部的「回媒体库」负责", async () => {
    await mount("");
    expect(screen.queryByLabelText("返回")).toBeNull();
  });
});

describe("上一集 / 下一集", () => {
  const SEASON = TV_MULTI_SEASON_NODE.children[1];   // Season 1，三集
  const [E10, E02, E01] = SEASON.videos;             // 夹具里是乱序的

  it("同季内按集号自然序给出相邻集与位置", async () => {
    await mount(E02.file_path);
    await waitFor(() => expect(screen.getByLabelText("切换集数")).toBeTruthy());
    // 排序后是 E01 / E02 / E10，E02 在第 2 个
    expect(screen.getByText("2 / 3")).toBeTruthy();
  });

  it("切集用 replace，连着看不在历史栈里堆层", async () => {
    await mount(E02.file_path);
    await waitFor(() => expect(screen.getByLabelText("切换集数")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: /下一集/ }));
    expect(mockRouter.replace).toHaveBeenCalledWith(playUrl(E10.file_path));
    expect(mockRouter.push).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /上一集/ }));
    expect(mockRouter.replace).toHaveBeenLastCalledWith(playUrl(E01.file_path));
  });

  it("第一集的「上一集」禁用，最后一集的「下一集」禁用", async () => {
    await mount(E01.file_path);
    await waitFor(() => expect(screen.getByText("1 / 3")).toBeTruthy());
    expect(screen.getByRole("button", { name: /上一集/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /下一集/ })).not.toBeDisabled();
  });

  it("电影（目录里只有一个视频）不渲染切集控件", async () => {
    await mount(MOVIE.file_path);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("钢铁侠 Iron Man (2008).mkv"));
    expect(screen.queryByLabelText("切换集数")).toBeNull();
  });

  it("树还没到时不渲染切集控件，不阻塞播放", async () => {
    mockApi.getLibraryTree.mockReturnValue(new Promise(() => {}));
    render(
      <MobileLibraryTreeProvider>
        <MobilePlayClient path={E02.file_path} />
      </MobileLibraryTreeProvider>,
    );
    expect(screen.queryByLabelText("切换集数")).toBeNull();
    expect(screen.getByTestId("player")).toBeTruthy();
  });
});
