// 字幕覆盖层：解析 VTT 内容，根据当前播放时间渲染对应字幕
"use client";
import { useState, useEffect, useRef } from "react";

interface Cue {
  start: number;  // 秒
  end: number;
  text: string;
}

interface SubtitleOverlayProps {
  vttContent: string;    // WebVTT 格式的字幕内容
  currentTime: number;   // 当前播放时间（秒）
  visible: boolean;      // 是否显示
  /** 用于按视频显示高度算字号，不传则退化为固定字号 */
  videoRef?: React.RefObject<HTMLVideoElement | null>;
  /** 距底部距离（px）。mp4 用原生 controls，要抬高避免被挡 */
  bottomOffset?: number;
}

export function SubtitleOverlay({
  vttContent, currentTime, visible, videoRef, bottomOffset = 48,
}: SubtitleOverlayProps) {
  const [cues, setCues] = useState<Cue[]>([]);
  const [fontSize, setFontSize] = useState(20);

  // 解析 VTT 内容
  useEffect(() => {
    if (!vttContent) { setCues([]); return; }
    setCues(parseVTT(vttContent));
  }, [vttContent]);

  // 字号跟视频显示高度成比例（约 4.5%），和浏览器原生 cue 的缩放行为一致。
  // 固定 px 的话小窗口糊成一团、全屏又小得看不清。
  useEffect(() => {
    const el = videoRef?.current;
    if (!el) return;
    const update = () => {
      const h = el.clientHeight || 0;
      if (h > 0) setFontSize(Math.round(Math.max(14, Math.min(44, h * 0.045))));
    };
    update();

    // ResizeObserver 在部分环境（jsdom、老浏览器）不存在，缺失时退化为
    // 只在全屏切换和窗口缩放时重算，不要因此整个组件崩掉
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(update);
      ro.observe(el);
    }
    window.addEventListener("resize", update);
    document.addEventListener("fullscreenchange", update);
    return () => {
      ro?.disconnect();
      window.removeEventListener("resize", update);
      document.removeEventListener("fullscreenchange", update);
    };
  }, [videoRef]);

  if (!visible || cues.length === 0) return null;

  // 找到当前时间对应的 cue
  const activeCues = cues.filter(c => currentTime >= c.start && currentTime <= c.end);

  if (activeCues.length === 0) return null;

  return (
    <div
      className="absolute left-0 right-0 flex flex-col items-center pointer-events-none px-4 z-30"
      style={{ bottom: `${bottomOffset}px` }}
    >
      {activeCues.map((cue, i) => (
        <div key={i} className="bg-black/75 text-white px-4 py-1.5 rounded mb-1 max-w-[85%] text-center"
          style={{ fontSize: `${fontSize}px`, lineHeight: 1.4 }}
          dangerouslySetInnerHTML={{ __html: sanitizeCueText(cue.text) }}
        />
      ))}
    </div>
  );
}

function parseVTT(content: string): Cue[] {
  const cues: Cue[] = [];
  const lines = content.split("\n");
  let i = 0;

  // 跳过 WEBVTT header 和空行
  while (i < lines.length && !lines[i].includes("-->")) i++;

  while (i < lines.length) {
    const line = lines[i].trim();

    // 时间轴行：00:01:11.369 --> 00:01:18.241
    if (line.includes("-->")) {
      const [startStr, endStr] = line.split("-->").map(s => s.trim());
      const start = parseTime(startStr);
      const end = parseTime(endStr);

      // 收集文本行（直到下一个时间轴行或纯数字序号+时间轴的组合）
      i++;
      const textLines: string[] = [];
      while (i < lines.length) {
        const nextLine = lines[i].trim();
        // 下一个 cue 开始的标志：纯数字行后面紧跟时间轴行
        if (/^\d+$/.test(nextLine) && i + 1 < lines.length && lines[i + 1].includes("-->")) {
          break;
        }
        // 或者直接遇到时间轴行
        if (nextLine.includes("-->")) break;
        // 跳过空行但不作为 cue 结束（兼容非标准 SRT）
        if (nextLine) textLines.push(nextLine);
        i++;
      }

      if (start >= 0 && end > start && textLines.length > 0) {
        cues.push({ start, end, text: textLines.join("\n") });
      }
    } else {
      i++;
    }
  }

  return cues;
}

function parseTime(str: string): number {
  // 支持 HH:MM:SS.mmm 和 MM:SS.mmm
  const parts = str.split(":");
  if (parts.length === 3) {
    const h = parseInt(parts[0], 10);
    const m = parseInt(parts[1], 10);
    const s = parseFloat(parts[2]);
    return h * 3600 + m * 60 + s;
  } else if (parts.length === 2) {
    const m = parseInt(parts[0], 10);
    const s = parseFloat(parts[1]);
    return m * 60 + s;
  }
  return -1;
}

function sanitizeCueText(text: string): string {
  // 保留 <b> <i> <u>，去掉其他 HTML 标签，换行变 <br>
  return text
    .replace(/<(?!\/?(?:b|i|u|br)\b)[^>]+>/gi, "")
    .replace(/\n/g, "<br>");
}
