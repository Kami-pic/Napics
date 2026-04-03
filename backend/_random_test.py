"""随机抽取文件夹做完整整理测试，输出详细结果"""
import sys, os, random, zipfile
sys.path.insert(0, '.')
import analyzer, organizer, scraper, tmdb_client, config_manager
from shadow_name_manager import ShadowNameManager

config_m = config_manager.ConfigManager()
library = config_m.load_library()
client = tmdb_client.TMDBClient(config_m.config.tmdb_api_key, proxy=config_m.config.http_proxy or '')

NAS = r"\\DS218play\share\视频"
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

# 收集所有候选文件夹（3-10个视频，之前没测过的）
tested = {"切尔诺贝利S1","方子传TV版","龙之家族第一季","灵探特莱丝.Trese.S01",
          "银翼杀手：黑莲花","特别的她","来自深渊剧场版三部曲","壳中少女 Mardock Scramble",
          "哥斯拉动画电影","better call saul s5","指环王：力量之戒",
          "福音战士新剧场版 Evangelion 三部曲","经典电影之新世代诠释 Reframed Next Gen Narratives",
          "永远之久远","魁拔—殊途"}

candidates = []
for top in ["电视剧","动画番","动画电影"]:
    tp = os.path.join(NAS, top)
    if not os.path.isdir(tp): continue
    for sub in os.listdir(tp):
        if sub in tested: continue
        sp = os.path.join(tp, sub)
        if not os.path.isdir(sp) or sub.startswith('.'): continue
        total = sum(1 for r,d,f in os.walk(sp) for fn in f if os.path.splitext(fn)[1].lower() in video_exts)
        if 3 <= total <= 10:
            candidates.append((top, sub, sp, total))

random.seed(42)
selected = random.sample(candidates, min(5, len(candidates)))

def restore_zip(path):
    zp = os.path.join(path, ".old_scrape.zip")
    if os.path.exists(zp):
        with zipfile.ZipFile(zp, 'r') as zf:
            zf.extractall(path)
        os.remove(zp)
    for d in os.listdir(path):
        dp = os.path.join(path, d)
        if os.path.isdir(dp):
            szp = os.path.join(dp, ".old_scrape.zip")
            if os.path.exists(szp):
                with zipfile.ZipFile(szp, 'r') as zf:
                    zf.extractall(dp)
                os.remove(szp)

def archive_dir(dir_path):
    scrape_names = {'poster.jpg','poster.png','fanart.jpg','fanart.png',
                    'clearlogo.png','folder.jpg','cover.jpg','movie.nfo',
                    'tvshow.nfo','season.nfo','theme.mp3'}
    poster_suffixes = ['-poster.jpg','-poster.png','-fanart.jpg','-fanart.png','-clearlogo.png','-thumb.jpg']
    files = []
    for f in os.listdir(dir_path):
        fp = os.path.join(dir_path, f)
        if not os.path.isfile(fp): continue
        ext = os.path.splitext(f)[1].lower()
        if f in scrape_names or ext == '.nfo' or \
           (ext in {'.jpg','.png'} and any(f.endswith(s) for s in poster_suffixes)):
            files.append(f)
    if not files: return 0
    zp = os.path.join(dir_path, '.old_scrape.zip')
    if os.path.exists(zp): return 0
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(os.path.join(dir_path, f), f)
    for f in files:
        try: os.remove(os.path.join(dir_path, f))
        except: pass
    return len(files)

print(f"随机抽取 {len(selected)} 个文件夹测试\n")

for top, name, path, vids in selected:
    print(f"{'='*60}")
    print(f"[{top}] {name} ({vids} videos)")
    print(f"{'='*60}")
    
    # 恢复旧刮削
    restore_zip(path)
    
    # 1. 备份删除旧刮削
    archived = archive_dir(path)
    for d in os.listdir(path):
        dp = os.path.join(path, d)
        if os.path.isdir(dp) and not d.startswith('.'):
            archived += archive_dir(dp)
    print(f"  旧刮削备份: {archived} 个文件")
    
    # 2. 分析
    report = analyzer.analyze_folder(path, library)
    ft = report.get("folder_type", "")
    struct_ops = len(report.get("structure_ops", []))
    print(f"  类型: {ft}")
    print(f"  结构操作: {struct_ops}")
    
    # 3. 刮削
    try:
        sr = scraper.scrape_folder(path, client, force=True)
        self_status = sr.get("self", {}).get("status", "")
        children = sr.get("children", [])
        child_ok = sum(1 for c in children if c.get("result",{}).get("self",{}).get("status") == "ok")
        child_fail = len(children) - child_ok
        print(f"  刮削: {self_status} (子项: {child_ok} ok, {child_fail} fail)")
    except Exception as e:
        print(f"  刮削: ERROR {str(e)[:50]}")
    
    # 4. 标准名
    rename_result = organizer.rename_videos_in_folder(path, client, dry_run=True, library_data=library)
    print(f"  标准名预览:")
    for r in rename_result[:6]:
        is_folder = "📁" if r.get("is_folder") else "🎬"
        shadow = r.get("shadow_name", "")[:50]
        old = r.get("old_name", "")[:35]
        unchanged = " (unchanged)" if r.get("unchanged") else ""
        print(f"    {is_folder} {old}{unchanged}")
        print(f"       → {shadow}")
    if len(rename_result) > 6:
        print(f"    ... +{len(rename_result)-6} more")
    
    # 恢复
    restore_zip(path)
    print()

print("测试完成")
