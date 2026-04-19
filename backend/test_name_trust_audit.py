"""2.0.2 旁路验证脚本 — 只读分析 media_library.json 的名称质量
⚠️ 安全保证：本脚本只读取 media_library.json，绝不写入任何文件。
输出报告写到 .kiro/docs/name-trust-audit.md"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LIBRARY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.json")
REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".kiro", "docs", "name-trust-audit.md")


def load_library_readonly():
    """只读加载 media_library.json"""
    if not os.path.exists(LIBRARY_PATH):
        print(f"[错误] 找不到 {LIBRARY_PATH}")
        sys.exit(1)
    with open(LIBRARY_PATH, "r", encoding="utf-8", errors="replace") as f:
        return json.load(f)


def is_low_quality_name(name: str) -> list:
    """检测低质量名称，返回问题列表"""
    issues = []
    if not name:
        issues.append("空名称")
        return issues
    # 纯数字
    if re.match(r'^\d+$', name.strip()):
        issues.append(f"纯数字: '{name}'")
    # 过短（中文≤1字，英文≤3字符）
    cn_chars = re.findall(r'[\u4e00-\u9fff]', name)
    en_part = re.sub(r'[\u4e00-\u9fff\d\s\.\-_]', '', name).strip()
    if cn_chars and len(cn_chars) <= 1 and not en_part:
        issues.append(f"过短: '{name}'")
    # 残留技术标签
    tech = ["x264", "x265", "hevc", "aac", "flac", "dts", "bluray", "webrip", "bdrip", "hdtv"]
    for t in tech:
        if t in name.lower():
            issues.append(f"残留技术标签: '{t}'")
            break
    # 残留广告
    ads = ["www.", "hltm", "66影视", "dygangs", "66ys", "最新电影"]
    for a in ads:
        if a.lower() in name.lower():
            issues.append(f"残留广告: '{a}'")
            break
    # 纯格式串（S01E01 等）
    if re.match(r'^S\d+E\d+$', name.strip(), re.I):
        issues.append(f"纯格式串: '{name}'")
    return issues


def analyze_shadow_overwrite_risk(item: dict) -> str:
    """检测 shadow_name 可能的错误覆盖风险"""
    shadow = item.get("shadow_name", "")
    source = item.get("shadow_name_source", "")
    clean = item.get("clean_name", "")
    if not shadow:
        return ""
    # 低质量 source 覆盖了看起来更好的 clean_name
    if source == "parsed" and clean and len(clean) > len(shadow) + 5:
        return f"parsed 覆盖风险: shadow='{shadow[:30]}' < clean='{clean[:30]}'"
    return ""


def analyze_clean_overwrite_simulation(item: dict) -> str:
    """模拟 safe_set_clean_name 的拦截效果：
    如果 clean_name 看起来像刮削结果（和 shadow_name 的中文部分一致），
    标记为 scrape 来源；否则标记为 parsed"""
    clean = item.get("clean_name", "")
    shadow = item.get("shadow_name", "")
    if not clean:
        return "empty"
    # 启发式推断来源
    if shadow:
        # 提取 shadow_name 的中文部分
        shadow_cn = "".join(re.findall(r'[\u4e00-\u9fff]', shadow))
        clean_cn = "".join(re.findall(r'[\u4e00-\u9fff]', clean))
        if shadow_cn and clean_cn and (shadow_cn in clean_cn or clean_cn in shadow_cn):
            return "likely_scrape"
    return "likely_parsed"


def main():
    print("[名称审计] 只读加载 media_library.json...")
    library = load_library_readonly()
    print(f"[名称审计] 共 {len(library)} 条记录")

    # 统计
    stats = {
        "total": len(library),
        "has_clean_name": 0,
        "has_shadow_name": 0,
        "has_clean_name_source": 0,
        "shadow_sources": {},
        "clean_quality_issues": [],
        "shadow_quality_issues": [],
        "overwrite_risks": [],
        "inferred_clean_source": {"likely_scrape": 0, "likely_parsed": 0, "empty": 0},
    }

    for item in library:
        cn = item.get("clean_name", "")
        sn = item.get("shadow_name", "")
        ss = item.get("shadow_name_source", "")
        cs = item.get("clean_name_source", "")

        if cn:
            stats["has_clean_name"] += 1
        if sn:
            stats["has_shadow_name"] += 1
        if cs:
            stats["has_clean_name_source"] += 1

        # shadow_name_source 分布
        stats["shadow_sources"][ss] = stats["shadow_sources"].get(ss, 0) + 1

        # clean_name 质量检查
        cn_issues = is_low_quality_name(cn)
        if cn_issues:
            stats["clean_quality_issues"].append({
                "file": item.get("file_name", "")[:50],
                "folder": item.get("folder_name", "")[:40],
                "clean_name": cn[:40],
                "issues": cn_issues,
            })

        # shadow_name 质量检查
        sn_issues = is_low_quality_name(sn) if sn else []
        if sn_issues:
            stats["shadow_quality_issues"].append({
                "file": item.get("file_name", "")[:50],
                "shadow_name": sn[:40],
                "source": ss,
                "issues": sn_issues,
            })

        # 覆盖风险
        risk = analyze_shadow_overwrite_risk(item)
        if risk:
            stats["overwrite_risks"].append({
                "file": item.get("file_name", "")[:50],
                "risk": risk,
            })

        # 推断 clean_name 来源
        inferred = analyze_clean_overwrite_simulation(item)
        stats["inferred_clean_source"][inferred] += 1

    # 生成报告
    lines = []
    lines.append("# [一次性] 名称可信度审计报告\n")
    lines.append(f"> 运行日期：2026-04-18")
    lines.append(f"> 数据源：backend/media_library.json（只读，未修改）")
    lines.append(f"> 记录总数：{stats['total']}\n")

    lines.append("## 1. 字段覆盖率\n")
    lines.append(f"| 字段 | 有值 | 占比 |")
    lines.append(f"|------|------|------|")
    lines.append(f"| clean_name | {stats['has_clean_name']} | {stats['has_clean_name']*100//max(stats['total'],1)}% |")
    lines.append(f"| shadow_name | {stats['has_shadow_name']} | {stats['has_shadow_name']*100//max(stats['total'],1)}% |")
    lines.append(f"| clean_name_source | {stats['has_clean_name_source']} | {stats['has_clean_name_source']*100//max(stats['total'],1)}% |")

    lines.append(f"\n## 2. shadow_name_source 分布\n")
    lines.append(f"| source | 数量 | 占比 |")
    lines.append(f"|--------|------|------|")
    for src, cnt in sorted(stats["shadow_sources"].items(), key=lambda x: -x[1]):
        label = src if src else "(空)"
        lines.append(f"| {label} | {cnt} | {cnt*100//max(stats['total'],1)}% |")

    lines.append(f"\n## 3. clean_name 来源推断（启发式）\n")
    lines.append(f"| 推断来源 | 数量 | 说明 |")
    lines.append(f"|----------|------|------|")
    for src, cnt in stats["inferred_clean_source"].items():
        desc = {"likely_scrape": "和 shadow_name 中文部分一致，可能来自刮削", "likely_parsed": "和 shadow_name 不一致，可能来自文件名清洗", "empty": "clean_name 为空"}
        lines.append(f"| {src} | {cnt} | {desc.get(src, '')} |")

    lines.append(f"\n## 4. clean_name 质量问题（{len(stats['clean_quality_issues'])} 个）\n")
    if stats["clean_quality_issues"]:
        lines.append(f"| # | 文件夹 | 文件名 | clean_name | 问题 |")
        lines.append(f"|---|--------|--------|------------|------|")
        for i, item in enumerate(stats["clean_quality_issues"][:30], 1):
            lines.append(f"| {i} | {item['folder']} | {item['file']} | {item['clean_name'] or '(空)'} | {'; '.join(item['issues'])} |")
        if len(stats["clean_quality_issues"]) > 30:
            lines.append(f"\n... 还有 {len(stats['clean_quality_issues']) - 30} 个问题\n")
    else:
        lines.append("无质量问题 ✅\n")

    lines.append(f"\n## 5. shadow_name 质量问题（{len(stats['shadow_quality_issues'])} 个）\n")
    if stats["shadow_quality_issues"]:
        lines.append(f"| # | 文件名 | shadow_name | source | 问题 |")
        lines.append(f"|---|--------|-------------|--------|------|")
        for i, item in enumerate(stats["shadow_quality_issues"][:20], 1):
            lines.append(f"| {i} | {item['file']} | {item['shadow_name']} | {item['source']} | {'; '.join(item['issues'])} |")
        if len(stats["shadow_quality_issues"]) > 20:
            lines.append(f"\n... 还有 {len(stats['shadow_quality_issues']) - 20} 个问题\n")
    else:
        lines.append("无质量问题 ✅\n")

    lines.append(f"\n## 6. 覆盖风险（{len(stats['overwrite_risks'])} 个）\n")
    if stats["overwrite_risks"]:
        lines.append(f"| # | 文件名 | 风险描述 |")
        lines.append(f"|---|--------|----------|")
        for i, item in enumerate(stats["overwrite_risks"][:20], 1):
            lines.append(f"| {i} | {item['file']} | {item['risk']} |")
    else:
        lines.append("无覆盖风险 ✅\n")

    report = "\n".join(lines)

    # 写报告（只写到 .kiro/docs/，不碰 media_library.json）
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n[名称审计] 报告已保存: {REPORT_PATH}")
    print(f"  clean_name 质量问题: {len(stats['clean_quality_issues'])}")
    print(f"  shadow_name 质量问题: {len(stats['shadow_quality_issues'])}")
    print(f"  覆盖风险: {len(stats['overwrite_risks'])}")


if __name__ == "__main__":
    main()
