// 窄屏时提示"有移动版可用"，用户自己决定去不去。
//
// **不做 UA 自动跳转**：UA 判断在平板、桌面窄窗口、iPad 请求桌面站点这些情况下必然误判，
// 而误判的代价是用户被锁在一个功能更少的界面里，且没有明显的回去入口。
//
// 挂在根 layout 上（而不是 / 和 /manage 各挂一次），所以要自己跳过 /m 与 /login。
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const DISMISS_KEY = "napics_mobile_hint_dismissed";

export default function MobileVersionHint() {
  const pathname = usePathname();
  // 初值 false：localStorage 只能在 effect 里读，首帧就渲染会让"已关闭"的用户看到一闪
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(DISMISS_KEY)) setVisible(true);
    } catch {
      setVisible(true);
    }
  }, []);

  const dismiss = () => {
    setVisible(false);
    try { localStorage.setItem(DISMISS_KEY, "1"); } catch {}
  };

  // 移动版自己不需要这条提示；登录页要保持干净
  if (!visible || pathname.startsWith("/m") || pathname.startsWith("/login")) return null;

  return (
    // md:hidden 而不是 JS 测宽度：转屏和改窗口宽度立刻生效，也不会有 SSR/CSR 宽度不一致
    <div className="fixed inset-x-3 bottom-3 z-50 flex items-center gap-3 rounded-xl border border-white/[0.06] bg-[#141414] px-3 py-2.5 shadow-lg md:hidden">
      <p className="min-w-0 flex-1 text-[13px] leading-snug text-slate-300">
        屏幕较窄，可以试试为手机做的移动版
      </p>
      <Link
        href="/m"
        className="shrink-0 rounded-lg bg-blue-600 px-3 py-2 text-[13px] font-medium text-white"
      >
        打开移动版
      </Link>
      <button
        type="button"
        onClick={dismiss}
        aria-label="不再提示"
        className="shrink-0 rounded-lg px-2 py-2 text-[13px] text-slate-500"
      >
        不再提示
      </button>
    </div>
  );
}
