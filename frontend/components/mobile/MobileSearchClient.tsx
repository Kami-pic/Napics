// /m/resource（资源搜索：BT / 磁力 / 网盘）的客户端外壳：
// 组装搜索头、两套结果视图和瞬时反馈。
//
// 它**不在底栏**，只从详情页的「搜索资源」「搜索升级」进来。底栏的「搜索」是
// /m/search（按片名找片子，见 MobileDiscoverSearchClient）。
// 页面只负责把 URL 参数规范化后交给这里，业务逻辑在 useMobileSearch。
"use client";
import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import type { EnhancedSearchResult, PanResult } from "@/types";
import { useMobileSearch } from "@/hooks/mobile/useMobileSearch";
import { useMobileConfig } from "./MobileProviders";
import { copyText } from "@/lib/mobile/clipboard";
import type { MobileSearchQuery } from "@/lib/mobile/mobileRouteUtils";
import MobileShell from "./MobileShell";
import MobileSearchHeader from "./MobileSearchHeader";
import MobileKeywordChain from "./MobileKeywordChain";
import MobileBtResults from "./MobileBtResults";
import MobilePanResults from "./MobilePanResults";
import MobileToast from "./MobileToast";
import { panShareText } from "./MobilePanResultItem";
import type { MobileSourceStatusItem, MobileSourceState } from "./MobileSourceStatusRow";

export interface MobileSearchClientProps {
  query: MobileSearchQuery;
}

export default function MobileSearchClient({ query }: MobileSearchClientProps) {
  const router = useRouter();
  const { search, draft, setDraft, submit, retry, switchTab, tab } = useMobileSearch(query);
  const { defaultSavePath } = useMobileConfig();
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  // 这一页一定是从别处 push 进来的（媒体库详情 / 发现详情 / 片名搜索），
  // 所以 back() 就是用户想要的"回上一页"。直达进来时底栏还在，不会成死屏 ——
  // 播放页那条"必须自带 fallback"的规则是因为它把底栏藏了。
  const onBack = useCallback(() => { router.back(); }, [router]);

  const btSources = useMemo<MobileSourceStatusItem[]>(
    () => Object.entries(search.sourceStatuses).map(([name, status]) => ({
      name,
      state: status.status as MobileSourceState,
      count: status.count ?? 0,
    })),
    [search.sourceStatuses],
  );

  const panSources = useMemo<MobileSourceStatusItem[]>(
    () => search.panSourceStatuses.map(status => ({
      name: status.name,
      state: status.status === "success"
        ? "done"
        : status.status === "disabled"
          ? "disabled"
          : "failed",
      count: status.count ?? 0,
    })),
    [search.panSourceStatuses],
  );

  const handleDownload = useCallback(async (result: EnhancedSearchResult) => {
    // 决策 C：P0 只有 qb 一个通道，不显示通道选择，也不调 recommendChannel
    await search.handleDownload(result, "qb");
  }, [search]);

  const handleCopy = useCallback(async (result: PanResult) => {
    // 链接和提取码一次给全：只复制链接的话换个 App 打开就进不去了
    const ok = await copyText(panShareText(result));
    setToast(ok === "ok"
      ? { msg: result.password ? "链接和提取码已复制" : "链接已复制", ok: true }
      : { msg: "复制失败，请长按链接手动复制", ok: false });
  }, []);

  const handleOpen = useCallback((result: PanResult) => {
    if (!result.share_url) {
      setToast({ msg: "这条结果没有分享链接", ok: false });
      return;
    }
    const opened = window.open(result.share_url, "_blank", "noopener,noreferrer");
    // 移动端浏览器常拦截非用户手势触发的新窗口，拦了要说一声
    if (!opened) setToast({ msg: "浏览器拦截了跳转，可先复制链接再打开", ok: false });
  }, []);

  const searchToast = search.toast;

  return (
    <MobileShell title="搜索资源" subtitle={query.q || undefined} onBack={onBack}>
      <MobileSearchHeader
        draft={draft}
        onDraftChange={setDraft}
        onSubmit={submit}
        tab={tab}
        onTabChange={switchTab}
        btCount={search.filtered.length}
        panCount={search.panResults.length}
      />

      {/* 搜索词回退链：搜完之后让用户看到到底拿哪些词搜的（网盘源不做回退链） */}
      {tab === "bt" && (
        <MobileKeywordChain
          sourceKeywordInfo={search.sourceKeywordInfo}
          searching={search.searching}
        />
      )}

      {tab === "bt" ? (
        <MobileBtResults
          results={search.filtered}
          searching={search.searching}
          error={search.error}
          hasQuery={!!query.q}
          sources={btSources}
          savePath={search.savePath}
          onSavePathChange={search.setSavePath}
          defaultSavePath={query.savePath || defaultSavePath}
          downloadingUrl={search.downloadingUrl}
          onDownload={result => { void handleDownload(result); }}
          onRetry={retry}
        />
      ) : (
        <MobilePanResults
          results={search.panResults}
          searching={search.panSearching}
          error={search.error}
          hasQuery={!!query.q}
          sources={panSources}
          onCopy={result => { void handleCopy(result); }}
          onOpen={handleOpen}
          onRetry={retry}
        />
      )}

      {/* 提交下载的结果反馈来自共享状态机，复制反馈是本页自己的 */}
      <MobileToast
        message={toast?.msg ?? searchToast?.msg ?? ""}
        ok={toast?.ok ?? searchToast?.ok ?? true}
        onDismiss={() => { setToast(null); search.setToast(null); }}
      />
    </MobileShell>
  );
}
