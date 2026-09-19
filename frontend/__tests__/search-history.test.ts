// 资源搜索历史：上限 10、去重置顶、可单删。
import { describe, it, expect, beforeEach } from "vitest";

import {
  readSearchHistory,
  pushSearchHistory,
  removeSearchHistory,
  SEARCH_HISTORY_LIMIT,
} from "@/lib/mobile/searchHistory";

describe("搜索历史", () => {
  beforeEach(() => { localStorage.clear(); });

  it("最近搜的排最前", () => {
    pushSearchHistory("沙丘");
    pushSearchHistory("三体");
    expect(readSearchHistory()).toEqual(["三体", "沙丘"]);
  });

  it("重复词去重并置顶，忽略大小写和首尾空格", () => {
    pushSearchHistory("Dune");
    pushSearchHistory("三体");
    pushSearchHistory("  dune  ");
    expect(readSearchHistory()).toEqual(["dune", "三体"]);
  });

  it("最多保留 10 条，超出丢最旧的", () => {
    for (let i = 0; i < 15; i++) pushSearchHistory(`kw${i}`);
    const list = readSearchHistory();
    expect(list.length).toBe(SEARCH_HISTORY_LIMIT);
    expect(list[0]).toBe("kw14");
    expect(list).not.toContain("kw4");
  });

  it("空词不写入", () => {
    pushSearchHistory("   ");
    expect(readSearchHistory()).toEqual([]);
  });

  it("单删只删指定词", () => {
    pushSearchHistory("沙丘");
    pushSearchHistory("三体");
    const after = removeSearchHistory("沙丘");
    expect(after).toEqual(["三体"]);
    expect(readSearchHistory()).toEqual(["三体"]);
  });

  it("坏数据不炸，返回空数组", () => {
    localStorage.setItem("napics_mobile_search_history", "{not json");
    expect(readSearchHistory()).toEqual([]);
  });
});
