// 滚动吸附 hook：三个吸附点
// 1. 下滑距墙 < 460px → 吸附到墙
// 2. 上滑从发现页接近墙 < 80px → 吸附到墙
// 3. 上滑距墙 > 260px → 吸附到顶
import { useEffect, useRef } from "react";

interface UseScrollDampingOptions {
  containerRef: React.RefObject<HTMLElement | null>;
  wallRef: React.RefObject<HTMLElement | null>;
  enabled: boolean;
}

export function useScrollDamping({
  containerRef, wallRef, enabled,
}: UseScrollDampingOptions) {
  const animatingRef = useRef(false);

  useEffect(() => {
    if (!enabled || !containerRef.current) return;
    const container = containerRef.current;
    let lastSt = container.scrollTop;

    const getWall = (): number => {
      if (!wallRef.current) return -1;
      const cr = container.getBoundingClientRect();
      const wr = wallRef.current.getBoundingClientRect();
      return Math.round(container.scrollTop + (wr.top - cr.top));
    };

    const smoothTo = (target: number, dur = 300) => {
      if (animatingRef.current) return;
      const start = container.scrollTop;
      const dist = target - start;
      if (Math.abs(dist) < 2) return;
      animatingRef.current = true;
      const t0 = performance.now();
      const step = (now: number) => {
        const p = Math.min((now - t0) / dur, 1);
        const ep = 1 - (1 - p) * (1 - p);
        container.scrollTop = Math.round(start + dist * ep);
        if (p < 1) requestAnimationFrame(step);
        else { container.scrollTop = Math.round(target); animatingRef.current = false; }
      };
      requestAnimationFrame(step);
    };

    const handleScroll = () => {
      if (animatingRef.current) return;
      const st = container.scrollTop;
      const dir = st - lastSt;
      lastSt = st;
      const wall = getWall();
      if (wall < 0) return;

      // 下滑：距墙 < 460px → 吸附到墙
      if (dir > 0 && st > wall - 460 && st < wall) {
        smoothTo(wall, 350);
        return;
      }

      // 上滑：从发现页接近墙 < 460px → 吸附到墙
      if (dir < 0 && st > wall && st < wall + 460) {
        smoothTo(wall, 250);
        return;
      }

      // 上滑：距墙 > 260px → 吸附到顶
      if (dir < 0 && st < wall - 260 && st > 0) {
        smoothTo(0, 200);
        return;
      }
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => container.removeEventListener("scroll", handleScroll);
  }, [enabled, containerRef, wallRef]);
}
