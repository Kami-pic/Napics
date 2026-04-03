"""全面审计：逐文件夹检查所有7步的每一个细节"""
import sys, os, re, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
import scraper, analyzer, organizer
from organizer import classify_folder, rename_videos_in_folder, _is_ignorable_subdir
from tmdb_client import parse_filename
import config_manager

config_m = config_manager.ConfigManager()
library = config_m.load_library()

NAS = r"\\DS218play\share\视频"
SKIP = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

all_issues = []

def check_folder(top, sub, sp, vids):
    """深度检查一个文件夹的所有问题"""
    issues = []
    ft = classify_folder(sp, library)
    folder_type = ft.get("type", "?")
    
    # ══ 1. 分类检查 ══
    # 单文件应该是 movie
    if vids == 1 and folder_type not in ("movie",):
        nfo = scraper.read_nfo(sp)
        mt = nfo.get("media_type","") if nfo else ""
        if mt not in ("tvshow","tv"):
            issues.append(f"[分类] 单文件={folder_type}，应为movie")
    
    # 动画电影目录下多文件无子目录不应该是 tv
    if top == "动画电影" and folder_type == "tv":
        subdirs = [d for d in os.listdir(sp) if os.path.isdir(os.path.join(sp,d)) and not d.startswith('.') and not _is_ignorable_subdir(d)]
        if not subdirs:
            issues.append(f"[分类] 动画电影下无子目录被判为tv，应为series_collection或mixed")
    
    # ══ 2. 结构检查 ══
    report = analyzer.analyze_folder(sp, library)
    struct_ops = report.get("structure_ops", [])
    wrap_ops = [op for op in struct_ops if op.get("action") == "wrap_in_folder"]
    move_ops = [op for op in struct_ops if op.get("action") in ("move", "move_to_subdir")]
    if wrap_ops:
        issues.append(f"[结构] {len(wrap_ops)}个视频需要包裹进独立文件夹")
    if move_ops:
        issues.append(f"[结构] {len(move_ops)}个文件需要移动")
    
    # ══ 3. 刮削检查 ══
    nfo = scraper.read_nfo(sp)
    has_folder_nfo = bool(nfo and nfo.get('tmdb_id'))
    
    # 检查子目录
    subdirs = []
    sub_no_nfo = []
    sub_wrong_nfo = []
    for d in sorted(os.listdir(sp)):
        dp = os.path.join(sp, d)
        if not os.path.isdir(dp) or d.startswith('.') or _is_ignorable_subdir(d):
            continue
        sub_vids = [f for f in os.listdir(dp) if os.path.isfile(os.path.join(dp,f)) and os.path.splitext(f)[1].lower() in video_exts]
        if not sub_vids:
            continue
        subdirs.append(d)
        snfo = scraper.read_nfo(dp)
        if not snfo or not snfo.get('tmdb_id'):
            sub_no_nfo.append(d)
        else:
            # 检查子目录刮削是否匹配
            stitle = snfo.get('title','')
            cn_parts = re.findall(r'[\u4e00-\u9fff]{2,}', d)
            en_parts = re.findall(r'[A-Za-z]{4,}', d)
            if cn_parts or en_parts:
                match = False
                for cp in cn_parts:
                    if cp in stitle: match = True
                for ep in en_parts:
                    if ep.lower() in stitle.lower() or ep.lower() in snfo.get('original_title','').lower() or ep.lower() in snfo.get('english_title','').lower():
                        match = True
                if not match and stitle:
                    sub_wrong_nfo.append(f"{d[:25]} -> {stitle[:20]}")
    
    if not has_folder_nfo and not subdirs:
        issues.append("[刮削] 无NFO")
    elif not has_folder_nfo and subdirs and not any(scraper.read_nfo(os.path.join(sp,d)) and scraper.read_nfo(os.path.join(sp,d)).get('tmdb_id') for d in subdirs):
        issues.append("[刮削] 文件夹和子目录都无NFO")
    
    if sub_no_nfo:
        issues.append(f"[刮削] {len(sub_no_nfo)}个子目录无NFO: {', '.join(s[:20] for s in sub_no_nfo[:3])}")
    if sub_wrong_nfo:
        issues.append(f"[刮削] 子目录匹配错误: {'; '.join(sub_wrong_nfo[:3])}")
    
    # 文件夹级刮削匹配检查
    if has_folder_nfo:
        nfo_title = nfo.get("title","")
        nfo_mt = nfo.get("media_type","")
        cn_parts = re.findall(r'[\u4e00-\u9fff]{2,}', sub)
        en_parts = re.findall(r'[A-Za-z]{4,}', sub)
        
        # 聚合文件夹不应该有文件夹级刮削（除非是 tv 类型）
        if folder_type in ("mixed","movie_collection","series_collection") and nfo_mt not in ("tvshow","tv"):
            # 聚合文件夹有 movie.nfo 是错的
            pass  # 这个情况比较复杂，先不报
        
        # 检查匹配
        match = False
        for cp in cn_parts:
            if cp in nfo_title: match = True
        for ep in en_parts:
            nfo_en = nfo.get('original_title','') + ' ' + nfo.get('english_title','')
            if ep.lower() in nfo_en.lower() or ep.lower() in nfo_title.lower(): match = True
        if not match and cn_parts and nfo_title:
            issues.append(f"[刮削] 文件夹匹配可疑: '{cn_parts[0]}' vs '{nfo_title[:25]}'")
    
    # ══ 4. 标准名检查 ══
    rename_result = rename_videos_in_folder(sp, None, dry_run=True, library_data=library)
    video_results = [r for r in rename_result if not r.get("is_folder")]
    
    if video_results:
        shadows = [r.get("shadow_name","") for r in video_results]
        
        # 所有影子名一样（tv类型多集不应该）
        if len(set(shadows)) == 1 and len(shadows) > 1:
            issues.append(f"[命名] 所有{len(shadows)}个视频影子名完全一样: '{shadows[0][:35]}'")
        
        # tv类型缺集号
        if folder_type == "tv" and vids > 1:
            no_ep = [s for s in shadows if s and not re.search(r'S\d+E\d+', s)]
            if no_ep and len(no_ep) > len(shadows) * 0.3:
                issues.append(f"[命名] {len(no_ep)}/{len(shadows)}个视频无集号")
        
        # 影子名质量
        for r in video_results:
            sn = r.get("shadow_name","")
            old = r.get("old_name","")
            
            # 含hash
            if re.search(r'\([A-F0-9]{6,}\)', sn):
                issues.append(f"[命名] 含hash: '{sn[:40]}'")
                break
            # 含URL/广告
            if re.search(r'www\.|http|影视|首发|电影天堂', sn, re.I):
                issues.append(f"[命名] 含广告: '{sn[:40]}'")
                break
            # 含方括号
            if '[' in sn and ']' in sn:
                issues.append(f"[命名] 含方括号: '{sn[:40]}'")
                break
            # 影子名就是文件夹名（没有独立刮削）
            if sn == sub and folder_type in ("mixed","series_collection","movie_collection"):
                issues.append(f"[命名] 聚合文件夹视频用了文件夹名: '{sn[:35]}'")
                break
        
        # 检查是否有视频用了父文件夹名而非自己的名字（聚合文件夹的问题）
        if folder_type in ("mixed","series_collection","movie_collection"):
            folder_name_used = sum(1 for s in shadows if s and sub[:6] in s[:10])
            if folder_name_used > len(shadows) * 0.5 and len(shadows) > 2:
                issues.append(f"[命名] 聚合文件夹{folder_name_used}/{len(shadows)}个视频用了父文件夹名")
    
    # ══ 5. 递归检查子目录的视频刮削 ══
    for d in subdirs:
        dp = os.path.join(sp, d)
        for f in os.listdir(dp):
            fp = os.path.join(dp, f)
            if not os.path.isfile(fp) or os.path.splitext(f)[1].lower() not in video_exts:
                continue
            vnfo = scraper.read_video_nfo(fp)
            if vnfo and vnfo.get('tmdb_id'):
                vtitle = vnfo.get('title','')
                # 检查视频NFO是否和子目录名匹配
                d_cn = re.findall(r'[\u4e00-\u9fff]{2,}', d)
                if d_cn and vtitle and d_cn[0] not in vtitle:
                    d_en = re.findall(r'[A-Za-z]{4,}', d)
                    v_en = vnfo.get('original_title','') + ' ' + vnfo.get('english_title','')
                    en_ok = any(e.lower() in v_en.lower() for e in d_en if len(e)>=4)
                    if not en_ok:
                        issues.append(f"[刮削] 视频NFO不匹配: {d[:20]}/{f[:20]} -> {vtitle[:20]}")
            break  # 只检查第一个视频
    
    return issues

# ── 主循环 ──
total = 0
for top in sorted(os.listdir(NAS)):
    tp = os.path.join(NAS, top)
    if not os.path.isdir(tp) or top.startswith('.') or top in SKIP:
        continue
    for sub in sorted(os.listdir(tp)):
        sp = os.path.join(tp, sub)
        if not os.path.isdir(sp) or sub.startswith('.'):
            continue
        vids = sum(1 for r,d,f in os.walk(sp) for fn in f if os.path.splitext(fn)[1].lower() in video_exts)
        if vids < 1:
            continue
        total += 1
        
        try:
            issues = check_folder(top, sub, sp, vids)
            if issues:
                ft = classify_folder(sp, library).get("type","?")
                all_issues.append((top, sub, vids, ft, issues))
        except Exception as e:
            all_issues.append((top, sub, vids, "?", [f"[错误] {str(e)[:60]}"]))

# ── 输出 ──
print(f"总文件夹: {total}, 有问题: {len(all_issues)}, 无问题: {total - len(all_issues)}")
print()

# 按问题类型统计
cats = {}
for _,_,_,_,issues in all_issues:
    for iss in issues:
        cat = re.match(r'\[([^\]]+)\]', iss)
        if cat:
            k = cat.group(1)
            cats[k] = cats.get(k, 0) + 1

print("问题分类统计:")
for k, v in sorted(cats.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}个")
print()

for top, name, vids, ft, issues in all_issues:
    print(f"[{top}] {name} ({vids}v, {ft})")
    for iss in issues:
        print(f"  {iss}")
    print()
