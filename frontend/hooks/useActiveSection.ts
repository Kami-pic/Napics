// 判定当前焦点落在媒体库还是发现区。
//
// 判据是「发现区吸附到容器顶部」，不是「发现区露出一点」：
// 首页停在媒体库根目录时，发现区本来就在下方露头，那时候焦点仍属于媒体库。
// 原来用 IntersectionObserver（threshold 0.05）判，一露头就把高亮抢走了。
import { useEffect, useState } from "react";

export type ActiveSection = "library" | "discover";

// 吸附动画收尾会差几像素，留一点容差
const SNAP_TOLERANCE_PX = 16;

interface UseActiveSectionOptions {
  containerRef: React.RefObject<HTMLElement | null>;
  /** 发现区容器（滚动吸附的那面「墙」） */
  wallRef: React.RefObject<HTMLElement | null>;
  /** 发现区是否存在。为 false 时焦点恒为媒体库 */
  enabled: boolean;
}

export function useActiveSection({
  containerRef, wallRef, enabled,
}: UseActiveSectionOptions): ActiveSection {
  const [active, setActive] = useState<ActiveSection>("library");

  useEffect(() => {
    const container = containerRef.current;
    if (!enabled || !container) { setActive("library"); return; }

    const update = () => {
      const wall = wallRef.current;
      if (!wall) { setActive("library"); return; }
      const offset = wall.getBoundingClientRect().top - container.getBoundingClientRect().top;
      setActive(offset <= SNAP_TOLERANCE_PX ? "discover" : "library");
    };

    update();
    container.addEventListener("scroll", update, { passive: true });
    return () => container.removeEventListener("scroll", update);
  }, [enabled, containerRef, wallRef]);

  return enabled ? active : "library";
}
