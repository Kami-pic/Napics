"""沙盒全量名称处理测试：遍历 sandbox_real 所有视频文件，
用 L1 process_text + parse_filename + _clean_filename_for_folder 处理，
生成"原始文件名 → 清洗后名称"的对比报告。"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from text_processing import process_text
from tmdb_client import parse_filename
from analyzer import _clean_filename_for_folder

SANDBOX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandbox_real")
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".ts", ".rmvb", ".rm", ".flv", ".wmv", ".mov", ".m4v"}


def collect_videos():
    """收集沙盒中所有视频文件"""
    videos = []
    for root, dirs, files in os.walk(SANDBOX):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in VIDEO_EXTS:
                rel = os.path.relpath(os.path.join(root, f), SANDBOX)
                folder = os.path.relpath(root, SANDBOX)
                videos.append({"file_name": f, "folder": folder, "rel_path": rel})
    return videos


def analyze_one(video: dict) -> dict:
    """对单个视频文件做全链路名称处理"""
    fn = video["file_name"]
    folder = video["folder"]

    # 1. _clean_filename_for_folder（当前系统用的清洗函数）
    clean_folder = _clean_filename_for_folder(fn)

    # 2. parse_filename（提取 clean_name / season / episode / year）
    parsed = parse_filename(fn)

    # 3. L1 process_text（新的文本处理模块）
    l1_result = process_text(fn)

    # 4. 也对文件夹名做 process_text
    folder_parts = folder.replace("/", "\\").split("\\")
    folder_name = folder_parts[-1] if folder_parts else folder
    l1_folder = process_text(folder_name)

    return {
        "file_name": fn,
        "folder": folder,
        "folder_name": folder_name,
        # 现有系统的清洗结果
        "clean_folder": clean_folder,
        "parsed_clean_name": parsed["clean_name"],
        "parsed_season": parsed["season"],
        "parsed_episode": parsed["episode"],
        "parsed_year": parsed["year"],
        # L1 新模块的处理结果
        "l1_normalized": l1_result["normalized"],
        "l1_cn": l1_result["cn"],
        "l1_en": l1_result["en"],
        "l1_language": l1_result["language"],
        "l1_is_short": l1_result["is_short_name"],
        # 文件夹名的 L1 处理
        "folder_l1_cn": l1_folder["cn"],
        "folder_l1_en": l1_folder["en"],
    }


def quality_check(result: dict) -> list:
    """检查名称质量问题"""
    issues = []
    cn = result["parsed_clean_name"]
    folder_cn = result["folder_l1_cn"]

    # 过短名称
    if cn and len(cn) <= 2 and not cn.isdigit():
        issues.append(f"过短: clean_name='{cn}'")
    # 纯数字
    if cn and cn.replace(" ", "").isdigit():
        issues.append(f"纯数字: clean_name='{cn}'")
    # clean_name 为空
    if not cn:
        issues.append("clean_name 为空")
    # clean_name 残留技术标签
    tech_tags = ["x264", "x265", "HEVC", "AAC", "FLAC", "DTS", "BluRay", "WEBRip", "BDRip"]
    for tag in tech_tags:
        if tag.lower() in cn.lower():
            issues.append(f"残留技术标签: '{tag}' in '{cn}'")
            break
    # clean_name 残留广告
    ad_tags = ["www.", "hltm", "66影视", "dygangs", "66Ys"]
    for tag in ad_tags:
        if tag.lower() in cn.lower():
            issues.append(f"残留广告: '{tag}' in '{cn}'")
            break
    return issues


def generate_report(results: list) -> str:
    """生成 Markdown 报告"""
    lines = []
    lines.append("# [一次性] 沙盒全量名称处理报告\n")
    lines.append(f"> 运行日期：2026-04-18")
    lines.append(f"> 沙盒路径：backend/sandbox_real/")
    lines.append(f"> 视频文件总数：{len(results)}\n")

    # 统计
    issues_count = 0
    issue_list = []
    categories = {}
    for r in results:
        cat = r["folder"].split("\\")[0] if "\\" in r["folder"] else r["folder"].split("/")[0]
        categories.setdefault(cat, []).append(r)
        issues = quality_check(r)
        if issues:
            issues_count += 1
            issue_list.append((r, issues))

    lines.append(f"## 总览\n")
    lines.append(f"| 分类 | 文件数 |")
    lines.append(f"|------|--------|")
    for cat in sorted(categories.keys()):
        lines.append(f"| {cat} | {len(categories[cat])} |")
    lines.append(f"| **合计** | **{len(results)}** |")
    lines.append(f"\n质量问题数：{issues_count} / {len(results)}\n")

    # 质量问题详情
    if issue_list:
        lines.append(f"## 质量问题\n")
        lines.append(f"| # | 文件夹 | 文件名 | clean_name | 问题 |")
        lines.append(f"|---|--------|--------|------------|------|")
        for i, (r, issues) in enumerate(issue_list[:50], 1):
            fn_short = r["file_name"][:40] + "..." if len(r["file_name"]) > 40 else r["file_name"]
            folder_short = r["folder_name"][:25] + "..." if len(r["folder_name"]) > 25 else r["folder_name"]
            cn = r["parsed_clean_name"][:30] if r["parsed_clean_name"] else "(空)"
            lines.append(f"| {i} | {folder_short} | {fn_short} | {cn} | {'; '.join(issues)} |")
        if len(issue_list) > 50:
            lines.append(f"\n... 还有 {len(issue_list) - 50} 个问题未列出\n")

    # 每个分类抽样展示（每类最多 5 个，展示清洗前后对比）
    lines.append(f"\n## 清洗前后对比（每类抽样）\n")
    for cat in sorted(categories.keys()):
        items = categories[cat]
        # 每个文件夹只取第一个视频（避免同一剧集重复展示）
        seen_folders = set()
        samples = []
        for r in items:
            if r["folder_name"] not in seen_folders:
                seen_folders.add(r["folder_name"])
                samples.append(r)
            if len(samples) >= 8:
                break

        lines.append(f"\n### {cat}（{len(items)} 个文件，{len(seen_folders)} 个文件夹）\n")
        lines.append(f"| 文件夹 | 原始文件名 | clean_folder | parsed_clean | L1 cn | L1 en | 季 | 集 | 年 |")
        lines.append(f"|--------|-----------|-------------|-------------|-------|-------|---|---|---|")
        for r in samples:
            fn = r["file_name"][:35] + "..." if len(r["file_name"]) > 35 else r["file_name"]
            fd = r["folder_name"][:20] + "..." if len(r["folder_name"]) > 20 else r["folder_name"]
            cf = r["clean_folder"][:20] + "..." if len(r["clean_folder"]) > 20 else r["clean_folder"]
            pc = r["parsed_clean_name"][:20] + "..." if len(r["parsed_clean_name"]) > 20 else r["parsed_clean_name"]
            cn = r["l1_cn"][:15] + "..." if len(r["l1_cn"]) > 15 else r["l1_cn"]
            en = r["l1_en"][:15] + "..." if len(r["l1_en"]) > 15 else r["l1_en"]
            s = r["parsed_season"] or ""
            e = r["parsed_episode"] or ""
            y = r["parsed_year"] or ""
            lines.append(f"| {fd} | {fn} | {cf} | {pc} | {cn} | {en} | {s} | {e} | {y} |")

    return "\n".join(lines)


if __name__ == "__main__":
    print("[沙盒名称测试] 收集视频文件...")
    videos = collect_videos()
    print(f"[沙盒名称测试] 找到 {len(videos)} 个视频文件")

    print("[沙盒名称测试] 处理中...")
    results = []
    errors = []
    for v in videos:
        try:
            r = analyze_one(v)
            results.append(r)
        except Exception as ex:
            errors.append({"file": v["file_name"], "error": str(ex)})

    print(f"[沙盒名称测试] 处理完成: {len(results)} 成功, {len(errors)} 失败")

    if errors:
        print("\n失败列表:")
        for e in errors[:10]:
            print(f"  {e['file']}: {e['error']}")

    # 生成报告
    report = generate_report(results)
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", ".kiro", "docs", "sandbox-name-report.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n报告已保存: {report_path}")

    # 也输出 JSON 供后续分析
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "sandbox_name_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"JSON 已保存: {json_path}")
