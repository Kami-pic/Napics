"""测试清洗函数效果：收集所有文件夹名+视频文件名，跑 _clean_filename_for_folder"""
import sys, os, json
sys.path.insert(0, '.')
from analyzer import _clean_filename_for_folder

NAS = r"\\DS218play\share\视频"
SKIP_DIRS = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

results = []

for top in sorted(os.listdir(NAS)):
    tp = os.path.join(NAS, top)
    if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
        continue
    for sub in sorted(os.listdir(tp)):
        sp = os.path.join(tp, sub)
        if not os.path.isdir(sp) or sub.startswith('.'):
            continue
        
        # 清洗文件夹名
        cleaned = _clean_filename_for_folder(sub)
        if cleaned != sub:
            results.append({"type": "folder", "original": sub, "cleaned": cleaned, "category": top})
        
        # 清洗视频文件名（只取前3个）
        videos = []
        for item in os.listdir(sp):
            fp = os.path.join(sp, item)
            if os.path.isfile(fp) and os.path.splitext(item)[1].lower() in video_exts:
                videos.append(item)
        
        for vf in videos[:3]:
            vc = _clean_filename_for_folder(vf)
            results.append({"type": "video", "original": vf, "cleaned": vc, "folder": sub, "category": top})

# 输出
print(f"总共 {len(results)} 条清洗结果\n")

# 找出可能有问题的（清洗后仍含质量标签/广告/方括号等）
import re
problems = []
for r in results:
    c = r["cleaned"]
    issues = []
    if re.search(r'\[', c):
        issues.append("残留方括号")
    if re.search(r'【', c):
        issues.append("残留中文方括号")
    if re.search(r'(?i)(1080p|720p|2160p|x264|x265|HEVC|AAC|DTS|FLAC|BluRay|WEB.?DL|HDTV|BDRip|Remux)', c):
        issues.append("残留质量标签")
    if re.search(r'(?i)(www\.|\.com|\.net|\.cc)', c):
        issues.append("残留URL")
    if re.search(r'[A-Fa-f0-9]{8}', c):
        issues.append("疑似hash")
    if not c.strip():
        issues.append("清洗后为空")
    if len(c) > 60:
        issues.append("过长")
    if re.search(r'(?i)\b(BD|HD|DVD)\b', c) and r["type"] == "video":
        issues.append("残留BD/HD/DVD")
    if re.search(r'_', c):
        issues.append("残留下划线")
    # 检查是否只剩数字
    if re.match(r'^\d+$', c.strip()):
        issues.append("只剩数字")
    # 检查残留的编码信息
    if re.search(r'(?i)(10bit|AVC|Main10|HEVC_Main)', c):
        issues.append("残留编码信息")
    if issues:
        r["issues"] = issues
        problems.append(r)

print(f"有问题的: {len(problems)} 条\n")
for p in problems:
    print(f"  [{p.get('category','')}] {p['type']}")
    print(f"    原始: {p['original'][:80]}")
    print(f"    清洗: {p['cleaned'][:80]}")
    print(f"    问题: {', '.join(p['issues'])}")
    print()

# 也输出所有文件夹级清洗结果供人工检查
print(f"\n{'='*60}")
print(f"所有文件夹清洗结果:\n")
for r in results:
    if r["type"] == "folder":
        print(f"  [{r['category']}]")
        print(f"    原始: {r['original'][:80]}")
        print(f"    清洗: {r['cleaned'][:80]}")
        print()
