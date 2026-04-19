// 工具函数

/** 格式化文件大小：<1G 显示 MB，>=1G 显示 GB */
export function formatSize(gb: number): string {
  if (gb < 1) return `${Math.round(gb * 1024)}M`;
  return `${gb.toFixed(1)}G`;
}

/** 格式化时长（分钟 → x时xxmin） */
export function formatDuration(min: number): string {
  if (!min || min <= 0) return "—";
  if (min < 60) return `${Math.round(min)}min`;
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m > 0 ? `${h}h${m}min` : `${h}h`;
}

/** 判断文件夹是否是末端（没有子文件夹，只有视频） */
export function isLeafFolder(node: { children: any[]; videos: any[] }): boolean {
  return (!node.children || node.children.length === 0) && node.videos && node.videos.length > 0;
}

/** 判断末端文件夹是否是剧集（视频文件名有集号特征） */
export function isSeriesFolder(node: { children: any[]; videos: any[] }): boolean {
  if (!isLeafFolder(node)) return false;
  if (node.videos.length < 2) return false;
  // 检查是否有 >=50% 的文件名包含集号特征
  const epPattern = /(?:E\d{1,3}|EP\d{1,3}|第\d{1,3}[集话]|\b\d{2,3}\b(?=\.\w{3}$)|S\d+E\d+)/i;
  const matchCount = node.videos.filter((v: any) => epPattern.test(v.file_name)).length;
  return matchCount >= node.videos.length * 0.5;
}

/** 获取文件夹深度（相对于根） */
export function getFolderDepth(path: string): number {
  if (!path) return 0;
  return path.replace(/\\/g, "/").split("/").filter(Boolean).length;
}

/** 中英文分离（和后端 L1 splitByLanguage 逻辑一致）
 * 数字/字母紧邻中文时归入中文（如 "91天" → cn="91天"，"JOJO的奇妙冒险" → cn="JOJO的奇妙冒险"）
 * 独立的英文单词归入英文 */
export function splitByLanguage(text: string): { cn: string; en: string } {
  if (!text) return { cn: "", en: "" };
  const CJK_RE = /[\u4e00-\u9fff\u3400-\u4dbf]+/;
  const ALPHA_RE = /^[a-zA-Z]+$/;
  const DIGIT_RE = /^[0-9]+$/;
  // 拆分为 token 序列
  const tokens = text.match(/[\u4e00-\u9fff\u3400-\u4dbf]+|[a-zA-Z]+|[0-9]+|[^\u4e00-\u9fff\u3400-\u4dbfa-zA-Z0-9]+/g) || [];
  const cnParts: string[] = [];
  const enParts: string[] = [];
  for (let i = 0; i < tokens.length; i++) {
    const tok = tokens[i];
    const isCjk = CJK_RE.test(tok);
    const isAlpha = ALPHA_RE.test(tok);
    const isDigit = DIGIT_RE.test(tok);
    if (isCjk) {
      cnParts.push(tok);
    } else if (isAlpha) {
      const prevCjk = i > 0 && CJK_RE.test(tokens[i - 1]);
      const nextCjk = i < tokens.length - 1 && CJK_RE.test(tokens[i + 1]);
      if (prevCjk || nextCjk) cnParts.push(tok);
      else enParts.push(tok);
    } else if (isDigit) {
      const prevCjk = i > 0 && CJK_RE.test(tokens[i - 1]);
      const nextCjk = i < tokens.length - 1 && CJK_RE.test(tokens[i + 1]);
      if (prevCjk || nextCjk) cnParts.push(tok);
      else enParts.push(tok);
    }
  }
  return { cn: cnParts.join(""), en: enParts.join(" ").replace(/\s+/g, " ").trim() };
}
