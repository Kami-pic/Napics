"""深度检查：逐文件夹验证整理7步的每一项结果"""
import sys, os, re, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
import scraper, analyzer, organizer
from organizer import classify_folder, rename_videos_in_folder
from tmdb_client import parse_filename
import config_manager

config_m = config_manager.ConfigManager()
library = config_m.load_library()

NAS = r"\\DS218play\share\视频"
SKIP = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

all_issues = []

for top in sorted(os.listdir(NAS)):
    tp = os.path.join(NAS, top)
    if not os.path.isdir(tp) or top.startswith('.') or top in SKIP:
        continue
    for sub in sorted(os.listdir(tp)):
        sp = os.path.join(tp, sub)
        if not os.path.isdir(sp) or sub.startswith('.'):
            continue
        vids = sum(1 for r, d, f in os.walk(sp) for fn in f if os.path.splitext(fn)[1].lower() in video_exts)
        if vids < 1:
            continue

        issues = []

        # ── 1. 分类检查 ──
        ft = classify_folder(sp, library)
        folder_type = ft.get("type", "?")
        
        # 动画电影目录下的应该是 series_collection 或 movie，不应该是 tv
        if top == "动画电影" and folder_type == "tv" and vids <= 10:
            issues.append(f"TYPE: {folder_type}(动画电影目录下不应为tv)")
        # 电影目录下单文件应该是 movie
        if top == "电影" and vids == 1 and folder_type != "movie":
            issues.append(f"TYPE: {folder_type}(单文件应为movie)")

        # ── 2. 结构检查 ──
        # 检查是否有散落视频（应该被包裹的没包裹）
        report = analyzer.analyze_folder(sp, library)
        struct_ops = report.get("structure_ops", [])
        if struct_ops:
            wrap_count = sum(1 for op in struct_ops if op.get("action") == "wrap_in_folder")
            move_count = sum(1 for op in struct_ops if op.get("action") == "move")
            if wrap_count > 0:
                issues.append(f"STRUCT: {wrap_count} videos need wrapping")
            if move_count > 0:
                issues.append(f"STRUCT: {move_count} files need moving")

        # ── 3. 刮削检查 ──
        nfo = scraper.read_nfo(sp)
        has_folder_nfo = bool(nfo and nfo.get('tmdb_id'))
        
        # 检查刮削匹配是否合理
        if has_folder_nfo:
            nfo_title = nfo.get("title", "")
            # 提取文件夹名的中文核心
            cn_parts = re.findall(r'[\u4e00-\u9fff]{2,}', sub)
            if cn_parts:
                main_cn = cn_parts[0]
                # 严格检查：NFO title 和文件夹名完全无关
                if main_cn not in nfo_title and nfo_title not in sub:
                    # 再检查英文部分
                    en_parts = re.findall(r'[A-Za-z]{3,}', sub)
                    nfo_en = nfo.get("original_title", "") or nfo.get("english_title", "")
                    en_match = any(ep.lower() in nfo_en.lower() for ep in en_parts if len(ep) >= 4)
                    if not en_match:
                        issues.append(f"SCRAPE_MISMATCH: folder='{main_cn}' nfo='{nfo_title[:25]}'")
        else:
            # 检查子目录是否有刮削
            has_any_sub_nfo = False
            for d in os.listdir(sp):
                dp = os.path.join(sp, d)
                if os.path.isdir(dp) and not d.startswith('.'):
                    snfo = scraper.read_nfo(dp)
                    if snfo and snfo.get('tmdb_id'):
                        has_any_sub_nfo = True
                        break
            if not has_any_sub_nfo:
                issues.append("NO_SCRAPE")

        # ── 4. 标准名检查 ──
        rename_result = rename_videos_in_folder(sp, None, dry_run=True, library_data=library)
        video_results = [r for r in rename_result if not r.get("is_folder")]
        
        if video_results:
            # 检查集号缺失（仅 tv 类型）
            if folder_type == "tv" and vids > 1:
                no_ep = [r for r in video_results if r.get("shadow_name") and not re.search(r'S\d+E\d+', r["shadow_name"])]
                if no_ep and len(no_ep) > len(video_results) * 0.3:
                    sample = no_ep[0]["shadow_name"][:40]
                    issues.append(f"NO_EPISODE({len(no_ep)}/{len(video_results)}): '{sample}'")
            
            # 检查影子名质量：不应该包含乱码hash、广告URL、方括号残留
            for r in video_results[:5]:
                sn = r.get("shadow_name", "")
                if re.search(r'[A-F0-9]{8}', sn) and not re.search(r'S\d+E\d+', sn):
                    issues.append(f"BAD_SHADOW: '{sn[:40]}'")
                    break
                if 'www.' in sn.lower() or 'http' in sn.lower():
                    issues.append(f"URL_IN_SHADOW: '{sn[:40]}'")
                    break
                if re.search(r'\[.*\]', sn):
                    issues.append(f"BRACKET_IN_SHADOW: '{sn[:40]}'")
                    break
            
            # 检查所有视频影子名是否都一样（不应该，除非是电影合集每个都不同）
            shadows = [r.get("shadow_name", "") for r in video_results if r.get("shadow_name")]
            if shadows and len(set(shadows)) == 1 and len(shadows) > 1 and folder_type == "tv":
                issues.append(f"ALL_SAME_SHADOW({len(shadows)}): '{shadows[0][:35]}'")
            
            # 检查影子名是否和文件夹名完全无关（可能刮削匹配错误）
            folder_shadow = None
            for r in rename_result:
                if r.get("is_folder") and not r.get("is_subfolder"):
                    folder_shadow = r.get("shadow_name", "")
                    break
            if folder_shadow and has_folder_nfo:
                # 文件夹影子名应该包含 NFO title
                nfo_title = nfo.get("title", "")
                if nfo_title and nfo_title not in folder_shadow and folder_shadow not in nfo_title:
                    issues.append(f"FOLDER_SHADOW_MISMATCH: shadow='{folder_shadow[:30]}' nfo='{nfo_title[:20]}'")

        if issues:
            all_issues.append((top, sub, vids, folder_type, issues))

# ── 输出报告 ──
print(f"总文件夹: 191, 有问题: {len(all_issues)}")
print()

# 按问题类型分组统计
type_counts = {}
for _, _, _, _, issues in all_issues:
    for iss in issues:
        key = iss.split(":")[0].split("(")[0]
        type_counts[key] = type_counts.get(key, 0) + 1

print("问题类型统计:")
for k, v in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")
print()

print("详细列表:")
for top, name, vids, ft, issues in all_issues:
    print(f"[{top}] {name} ({vids} vids, type={ft})")
    for iss in issues:
        print(f"  - {iss}")
