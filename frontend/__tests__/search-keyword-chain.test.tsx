// 搜索词回退链：桌面弹窗与移动端资源搜索页共用一份汇总逻辑。
// 用户看到「没有结果」时第一个要问的是"你到底拿什么词搜的"。
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { buildKeywordChain } from "@/lib/domain/searchKeywords";
import MobileKeywordChain from "@/components/mobile/MobileKeywordChain";

describe("buildKeywordChain", () => {
  it("未命中的排在前面，命中的排在最后", () => {
    const chain = buildKeywordChain({
      nyaa: { searched: ["剃刀边缘 S01", "剃刀边缘"], hit: "剃刀边缘" },
    });
    expect(chain).toEqual([
      { keyword: "剃刀边缘 S01", hit: false },
      { keyword: "剃刀边缘", hit: true },
    ]);
  });

  it("多个源试过同一个词只显示一次", () => {
    const chain = buildKeywordChain({
      a: { searched: ["Dune", "Dune Part Two"], hit: "" },
      b: { searched: ["Dune", "沙丘"], hit: "沙丘" },
    });
    expect(chain.map(c => c.keyword)).toEqual(["Dune", "Dune Part Two", "沙丘"]);
    expect(chain.filter(c => c.hit).map(c => c.keyword)).toEqual(["沙丘"]);
  });

  it("一个源命中的词在另一个源没命中时，仍算命中（有结果就是有结果）", () => {
    const chain = buildKeywordChain({
      a: { searched: ["三体"], hit: "" },
      b: { searched: ["三体"], hit: "三体" },
    });
    expect(chain).toEqual([{ keyword: "三体", hit: true }]);
  });

  it("空输入与缺字段不炸", () => {
    expect(buildKeywordChain({})).toEqual([]);
    expect(buildKeywordChain({ a: { searched: [], hit: "" } })).toEqual([]);
    // 后端漏字段时也不能抛
    expect(buildKeywordChain({ a: undefined as never })).toEqual([]);
  });
});

describe("MobileKeywordChain", () => {
  const INFO = { nyaa: { searched: ["剃刀边缘 S01", "剃刀边缘"], hit: "剃刀边缘" } };

  it("搜完后显示整条链，命中项带对勾（不只靠颜色区分）", () => {
    render(<MobileKeywordChain sourceKeywordInfo={INFO} searching={false} />);
    expect(screen.getByLabelText("搜索词回退链")).toBeTruthy();
    expect(screen.getByText("剃刀边缘 S01")).toBeTruthy();
    expect(screen.getByLabelText("命中")).toBeTruthy();
  });

  it("搜索中不显示：链还不完整，会一直跳变", () => {
    render(<MobileKeywordChain sourceKeywordInfo={INFO} searching />);
    expect(screen.queryByLabelText("搜索词回退链")).toBeNull();
  });

  it("没有回退信息时什么都不渲染，不留空条", () => {
    render(<MobileKeywordChain sourceKeywordInfo={{}} searching={false} />);
    expect(screen.queryByLabelText("搜索词回退链")).toBeNull();
  });
});
