// 宽屏时提示"可以切回网页版"，用户自己决定去不去。
//
// 和根 layout 的 MobileVersionHint（web→移动）方向相反：那条挂在桌面壳上、窄屏显示；
// 这条挂在 /m 壳上、**宽屏才显示** —— 用户把手机横过来、或用平板/桌面浏览器打开了
// 移动版时，给一个回网页版的出口。同样不做 UA 自动跳转（误判代价是把用户锁在窄界面里）。
"use client";
import { useSyncExternalStore } from "react";

const DISMISS_KEY = "napics_desktop_hint_dismissed";

// 与 MobileVersionHint 同构：localStorage 是外部状态，用 useSyncExternalStore 读，
// getServerSnapshot 返回 true（SSR 当作已关闭），避免 SSR/CSR 不一致的一闪。
const listeners = new Set<() => void>();

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => { listeners.delete(onChange); };
}

function isDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISS_KEY) !== null;
  } catch {
    return false;
  }
}

function dismissForever() {
  try { localStorage.setItem(DISMISS_KEY, "1"); } catch {}
  for (const listener of listeners) listener();
}

export default function MobileToDesktopHint() {
  const dismissed = useSyncExternalStore(subscribe, isDismissed, () => true);
  if (dismissed) return null;

  return (
    // hidden md:flex 而不是 JS 测宽度：转屏和改窗口宽度立刻生效，也不会有
    // SSR/CSR 宽度不一致。窄屏（真手机）下这条根本不出现。
    // 用普通 <a>（不是 next/link）：/m 与 / 是同一 Next 应用的不同段，
    // 但要确保带上桌面 viewport，硬导航最省事，也和 MobileVersionHint 的 Link 反向对称。
    <div className="fixed inset-x-3 bottom-3 z-50 hidden items-center gap-3 rounded-xl border border-[var(--m-border)] bg-[var(--m-surface-raised)] px-3 py-2.5 shadow-lg md:flex">
      <p className="min-w-0 flex-1 text-[13px] leading-snug text-[var(--m-text)]">
        屏幕够宽，网页版功能更全（整理、批处理、洗版都在那边）
      </p>
      <a
        href="/"
        className="shrink-0 rounded-lg px-3 py-2 text-[13px] font-medium text-[var(--m-on-accent)]"
        style={{ background: "var(--m-accent)" }}
      >
        切到网页版
      </a>
      <button
        type="button"
        onClick={dismissForever}
        aria-label="不再提示"
        className="shrink-0 rounded-lg px-2 py-2 text-[13px] text-[var(--m-text-dim)]"
      >
        不再提示
      </button>
    </div>
  );
}
