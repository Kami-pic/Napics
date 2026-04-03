"""全量执行第2-4步：清空上次刮削 → 分析 → 结构归位 → 多季规整
保留第1步的 .old_scrape.zip 备份不动。
"""
import sys, os, time, json, traceback
sys.path.insert(0, '.')

import analyzer
import organizer
import config_manager
import tmdb_client

config_m = config_manager.ConfigManager()
library = config_m.load_library()
client = tmdb_client.TMDBClient(config_m.config.tmdb_api_key, proxy=config_m.config.http_proxy or '')

NAS = r"\\DS218play\share\视频"
SKIP_DIRS = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

SCRAPE_NAMES = {'poster.jpg', 'poster.png', 'fanart.jpg', 'fanart.png',
                'clearlogo.png', 'folder.jpg', 'cover.jpg', 'movie.nfo',
                'tvshow.nfo', 'season.nfo', 'theme.mp3'}
POSTER_SUFFIXES = ['-poster.jpg', '-poster.png', '-fanart.jpg',
                   '-fanart.png', '-clearlogo.png', '-thumb.jpg']


def is_scrape_file(f):
    """判断是否为刮削产生的文件（不含 .old_scrape.zip）"""
    if f == '.old_scrape.zip':
        return False
    ext = os.path.splitext(f)[1].lower()
    if f in SCRAPE_NAMES:
        return True
    if ext == '.nfo':
        return True
    if ext in {'.jpg', '.png'} and any(f.endswith(s) for s in POSTER_SUFFIXES):
        return True
    return False


def clean_scrape_files(folder_path, recursive=True):
    """清空上次整理产生的刮削文件，保留 .old_scrape.zip"""
    count = 0
    try:
        for f in os.listdir(folder_path):
            fp = os.path.join(folder_path, f)
            if os.path.isfile(fp) and is_scrape_file(f):
                os.remove(fp)
                count += 1
    except OSError:
        pass

    if recursive:
        try:
            for item in os.listdir(folder_path):
                sub = os.path.join(folder_path, item)
                if os.path.isdir(sub) and not item.startswith('.'):
                    count += clean_scrape_files(sub, recursive=True)
        except OSError:
            pass
    return count


def collect_folders():
    folders = []
    for top in sorted(os.listdir(NAS)):
        tp = os.path.join(NAS, top)
        if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
            continue
        for sub in sorted(os.listdir(tp)):
            sp = os.path.join(tp, sub)
            if not os.path.isdir(sp) or sub.startswith('.'):
                continue
            total = sum(1 for r, d, f in os.walk(sp) for fn in f
                        if os.path.splitext(fn)[1].lower() in video_exts)
            if total >= 1:
                folders.append({"category": top, "name": sub, "path": sp, "videos": total})
    return folders


def run_steps234(folder_path, execute=True):
    """清空刮削 → 第2步分析 → 第3步结构归位 → 第4步多季规整"""
    name = os.path.basename(folder_path)

    # 清空上次刮削（保留 .old_scrape.zip）
    cleaned = clean_scrape_files(folder_path, recursive=True)
    if cleaned:
        print(f"  清理了 {cleaned} 个刮削文件")

    # 第2步：分析
    report = analyzer.analyze_folder(folder_path, library)
    ft = report.get("folder_type", "")
    struct_ops = report.get("structure_ops", [])
    print(f"  类型: {ft}, 结构操作: {len(struct_ops)}")

    # 第3步：结构归位
    org_result = organizer.organize_folder(folder_path, client, dry_run=(not execute), library_data=library)
    ops = org_result.get("ops", [])
    move_ops = [op for op in ops if op.get("action") == "move"]
    if move_ops:
        print(f"  移动操作: {len(move_ops)}")
        for op in move_ops[:5]:
            print(f"    {os.path.basename(op.get('old',''))[:40]} → {os.path.basename(os.path.dirname(op.get('new','')))[:25]}/")
        if len(move_ops) > 5:
            print(f"    ... +{len(move_ops)-5} more")

    # 第4步：多季规整（仅 tv）
    reorg_count = 0
    if ft == "tv":
        reorg = organizer.reorganize_seasons(folder_path, client, dry_run=(not execute))
        reorg_ops = reorg.get("ops", [])
        reorg_count = len(reorg_ops)
        if reorg_ops:
            print(f"  多季规整: {reorg_count} 操作")

    return {
        "folder_type": ft,
        "cleaned": cleaned,
        "struct_ops": len(struct_ops),
        "move_ops": len(move_ops),
        "reorg_ops": reorg_count,
    }


def main():
    folders = collect_folders()
    print(f"总文件夹: {len(folders)}\n")

    # === 预处理：封装一级分类目录下的散落视频 ===
    print("=== 预处理：封装散落视频 ===")
    from organizer import wrap_loose_videos_in_category
    for top in sorted(os.listdir(NAS)):
        tp = os.path.join(NAS, top)
        if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
            continue
        result = wrap_loose_videos_in_category(tp, dry_run=False)
        if result["count"] > 0:
            print(f"  [{top}] 封装了 {result['count']} 个文件")
    
    # 清理残留的空 wrap 目录（只有 .old_scrape.zip）
    for top in sorted(os.listdir(NAS)):
        tp = os.path.join(NAS, top)
        if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
            continue
        for sub in os.listdir(tp):
            sp = os.path.join(tp, sub)
            if not os.path.isdir(sp) or sub.startswith('.'):
                continue
            for d in list(os.listdir(sp)):
                dp = os.path.join(sp, d)
                if os.path.isdir(dp) and not d.startswith('.'):
                    items = os.listdir(dp)
                    if items == ['.old_scrape.zip']:
                        os.remove(os.path.join(dp, '.old_scrape.zip'))
                        os.rmdir(dp)
    
    # 重新收集（封装后可能多了新文件夹）
    folders = collect_folders()
    print(f"\n封装后总文件夹: {len(folders)}\n")

    results = []
    errors = []

    for i, f in enumerate(folders):
        print(f"[{i+1}/{len(folders)}] [{f['category']}] {f['name']} ({f['videos']} vids)")
        t0 = time.time()
        try:
            r = run_steps234(f["path"], execute=True)
            elapsed = time.time() - t0
            r["name"] = f["name"]
            r["category"] = f["category"]
            r["elapsed"] = round(elapsed, 1)
            r["status"] = "ok"
            results.append(r)
            print(f"  OK {r['folder_type']} ({elapsed:.1f}s)")
        except Exception as e:
            elapsed = time.time() - t0
            errors.append({
                "name": f["name"],
                "category": f["category"],
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
            print(f"  ERR: {str(e)[:80]} ({elapsed:.1f}s)")

    # 汇总
    print(f"\n{'='*60}")
    print(f"第2-4步全量完成")
    print(f"成功: {len(results)}, 失败: {len(errors)}")

    # 统计
    type_counts = {}
    total_cleaned = 0
    total_moves = 0
    total_reorg = 0
    for r in results:
        ft = r.get("folder_type", "unknown")
        type_counts[ft] = type_counts.get(ft, 0) + 1
        total_cleaned += r.get("cleaned", 0)
        total_moves += r.get("move_ops", 0)
        total_reorg += r.get("reorg_ops", 0)

    print(f"\n类型分布: {json.dumps(type_counts, ensure_ascii=False)}")
    print(f"清理刮削: {total_cleaned} 文件")
    print(f"结构移动: {total_moves} 操作")
    print(f"多季规整: {total_reorg} 操作")

    if errors:
        print(f"\n失败列表:")
        for e in errors:
            print(f"  [{e['category']}] {e['name']}: {e['error'][:60]}")

    # 保存报告
    report = {
        "results": results,
        "errors": errors,
        "summary": {
            "type_counts": type_counts,
            "total_cleaned": total_cleaned,
            "total_moves": total_moves,
            "total_reorg": total_reorg,
        },
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open("_batch_steps234_report.json", "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: _batch_steps234_report.json")


if __name__ == "__main__":
    main()
