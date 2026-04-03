"""完整整理流水线 — 按操作指南8步执行
用法: python _organize_pipeline.py <folder_path> [--execute]
不加 --execute 只做 dry_run 预览
"""
import sys, os, json, zipfile, time
sys.path.insert(0, '.')

import analyzer
import organizer
import scraper
import tmdb_client
import config_manager
from shadow_name_manager import ShadowNameManager

config_m = config_manager.ConfigManager()
library = config_m.load_library()
client = tmdb_client.TMDBClient(config_m.config.tmdb_api_key, proxy=config_m.config.http_proxy or '')
shadow_m = ShadowNameManager()

def archive_old_scrape(folder_path, recursive=True, delete_after=True):
    """旧刮削打包为 .old_scrape.zip（每个文件夹各自打包）
    delete_after=False 时只打包不删除原文件（备份模式）
    """
    scrape_names = {'poster.jpg', 'poster.png', 'fanart.jpg', 'fanart.png',
                    'clearlogo.png', 'folder.jpg', 'cover.jpg', 'movie.nfo',
                    'tvshow.nfo', 'season.nfo', 'theme.mp3'}
    poster_suffixes = ['-poster.jpg', '-poster.png', '-fanart.jpg',
                       '-fanart.png', '-clearlogo.png', '-thumb.jpg']
    
    def _is_scrape_file(f):
        ext = os.path.splitext(f)[1].lower()
        return f in scrape_names or ext == '.nfo' or \
               (ext in {'.jpg', '.png'} and any(f.endswith(s) for s in poster_suffixes))
    
    def _archive_dir(dir_path):
        files_to_archive = []
        for f in os.listdir(dir_path):
            fp = os.path.join(dir_path, f)
            if os.path.isfile(fp) and _is_scrape_file(f):
                files_to_archive.append(f)
        
        if not files_to_archive:
            return 0
        
        zip_path = os.path.join(dir_path, '.old_scrape.zip')
        # 如果已有旧的 zip，追加或跳过
        if os.path.exists(zip_path):
            return 0
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in files_to_archive:
                zf.write(os.path.join(dir_path, f), f)
        
        for f in files_to_archive:
            if delete_after:
                os.remove(os.path.join(dir_path, f))
        
        return len(files_to_archive)
    
    total = _archive_dir(folder_path)
    
    if recursive:
        for item in os.listdir(folder_path):
            sub = os.path.join(folder_path, item)
            if os.path.isdir(sub) and not item.startswith('.'):
                total += _archive_dir(sub)
    
    return total


def run_pipeline(folder_path, execute=False):
    """执行完整整理流水线（8步）"""
    name = os.path.basename(folder_path)
    mode = "EXECUTE" if execute else "DRY_RUN"
    print(f"\n{'='*60}")
    print(f"📁 {name}")
    print(f"   模式: {mode}")
    print(f"   路径: {folder_path}")
    
    # === 第0步：散落视频封装（一级分类目录下的独立视频封装进文件夹）===
    print(f"\n--- 第0步：散落视频封装 ---")
    if execute:
        wrap_result = organizer.wrap_loose_videos_in_category(folder_path, dry_run=False)
        wrap_count = wrap_result.get("count", 0)
        if wrap_count > 0:
            print(f"   封装了 {wrap_count} 个文件")
        else:
            print(f"   无散落视频")
        # 清理残留的空 wrap 目录（只有 .old_scrape.zip）
        for item in os.listdir(folder_path):
            sub = os.path.join(folder_path, item)
            if os.path.isdir(sub) and not item.startswith('.'):
                sub_items = os.listdir(sub)
                if sub_items == ['.old_scrape.zip']:
                    os.remove(os.path.join(sub, '.old_scrape.zip'))
                    os.rmdir(sub)
    else:
        wrap_result = organizer.wrap_loose_videos_in_category(folder_path, dry_run=True)
        print(f"   将封装 {wrap_result.get('count', 0)} 个文件")
    
    # === 第1步：旧刮削备份（打包并删除，让后续分析基于纯文件结构）===
    print(f"\n--- 第1步：旧刮削备份 ---")
    if execute:
        archived = archive_old_scrape(folder_path, delete_after=True)
        print(f"   备份并清理了 {archived} 个旧刮削文件")
    else:
        print(f"   (dry_run 跳过)")
    
    # === 第2步：分析 ===
    print(f"\n--- 第2步：分析 ---")
    report = analyzer.analyze_folder(folder_path, library)
    ft = report.get("folder_type", "")
    struct_ops = report.get("structure_ops", [])
    rename_ops = report.get("rename_ops", [])
    scrape_issues = report.get("scrape_issues", [])
    fname_issues = report.get("filename_issues", [])
    print(f"   类型: {ft}")
    print(f"   结构操作: {len(struct_ops)}, 改名建议: {len(rename_ops)}")
    print(f"   刮削问题: {len(scrape_issues)}, 文件名问题: {len(fname_issues)}")
    
    # === 第3步：文件移动（结构归位）===
    print(f"\n--- 第3步：文件移动 ---")
    org_result = organizer.organize_folder(folder_path, client, dry_run=(not execute), library_data=library)
    ops = org_result.get("ops", [])
    move_ops = [op for op in ops if op.get("action") == "move"]
    print(f"   移动操作: {len(move_ops)}")
    for op in move_ops[:8]:
        old_name = os.path.basename(op.get("old", ""))
        new_parent = os.path.basename(os.path.dirname(op.get("new", "")))
        print(f"     {old_name[:40]} -> {new_parent[:25]}/")
    if len(move_ops) > 8:
        print(f"     ... +{len(move_ops)-8} more")
    
    # === 第4步：多季规整 ===
    print(f"\n--- 第4步：多季规整 ---")
    if ft == "tv":
        reorg = organizer.reorganize_seasons(folder_path, client, dry_run=(not execute))
        reorg_ops = reorg.get("ops", [])
        print(f"   规整操作: {len(reorg_ops)}")
    else:
        print(f"   跳过（非 tv 类型）")
    
    # === 第5步：刮削 ===
    print(f"\n--- 第5步：刮削 ---")
    scrape_ok = False
    if execute:
        scrape_result = scraper.scrape_folder(folder_path, client, force=True)
        self_status = scrape_result.get("self", {}).get("status", "")
        children = scrape_result.get("children", [])
        print(f"   自身: {self_status}")
        print(f"   子项: {len(children)}")
        for child in children[:5]:
            cn = child.get("name", "")
            cs = child.get("result", {}).get("self", {}).get("status", "")
            print(f"     {cn[:30]}: {cs}")
    else:
        print(f"   (dry_run 跳过刮削)")
    
    # === 第6步：改名预览（只存影子名，不改文件名）===
    print(f"\n--- 第6步：改名预览（只存影子名，不改文件名）---")
    rename_result = organizer.rename_videos_in_folder(folder_path, client, dry_run=True, library_data=library)
    changed = [r for r in rename_result if not r.get("unchanged")]
    unchanged = [r for r in rename_result if r.get("unchanged")]
    print(f"   建议改名: {len(changed)}, 已标准: {len(unchanged)}")
    for r in (changed + unchanged)[:10]:
        old = r.get("old_name", "")[:35]
        new = r.get("new_name", "")[:35]
        shadow = r.get("shadow_name", "")[:35]
        is_folder = "📁" if r.get("is_folder") else "🎬"
        marker = "" if not r.get("unchanged") else " (unchanged)"
        print(f"     {is_folder} {old}{marker}")
        print(f"        影子: {shadow}")
    if len(changed) + len(unchanged) > 10:
        print(f"     ... +{len(changed) + len(unchanged) - 10} more")
    
    # === 第7步：影子名 ===
    print(f"\n--- 第7步：影子名 ---")
    if execute:
        shadow_count = 0
        for r in rename_result:
            fp = r.get("old_path", "")
            shadow = r.get("shadow_name", "")
            if fp and shadow:
                if shadow_m.auto_fill(fp, shadow, source="parsed"):
                    shadow_count += 1
        print(f"   填充了 {shadow_count} 个影子名")
    else:
        shadow_candidates = [r for r in rename_result if r.get("shadow_name") and not r.get("is_folder")]
        print(f"   将填充 {len(shadow_candidates)} 个影子名")
    
    print(f"\n{'='*60}")
    return {"folder_type": ft, "struct_ops": len(struct_ops), "rename_changed": len(changed)}


if __name__ == "__main__":
    nas = r"\\DS218play\share\视频"
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test3":
        # 测试3个文件夹
        folders = [
            nas + r"\电影\经典电影之新世代诠释 Reframed Next Gen Narratives",
            nas + r"\电视剧\冰与火之歌1-8季",
            nas + r"\动画电影\永远之久远",
        ]
        execute = "--execute" in sys.argv
        for f in folders:
            run_pipeline(f, execute=execute)
    elif len(sys.argv) > 1:
        path = sys.argv[1]
        execute = "--execute" in sys.argv
        run_pipeline(path, execute=execute)
    else:
        print("用法: python _organize_pipeline.py --test3 [--execute]")
        print("      python _organize_pipeline.py <folder_path> [--execute]")
