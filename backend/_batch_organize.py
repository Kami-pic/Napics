"""全量整理 — 对所有文件夹执行完整7步流水线"""
import sys, os, time, json, traceback
sys.path.insert(0, '.')
from _organize_pipeline import run_pipeline, archive_old_scrape

NAS = r"\\DS218play\share\视频"
SKIP_DIRS = {"其他视频"}  # 跳过非影视目录

# 已经在之前测试中成功执行过的（有正确刮削+影子名）
ALREADY_DONE = set()  # 重新跑全部，影子名之前都失败了需要重填

video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

def collect_folders():
    """收集所有待处理文件夹"""
    folders = []
    for top in sorted(os.listdir(NAS)):
        tp = os.path.join(NAS, top)
        if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
            continue
        for sub in sorted(os.listdir(tp)):
            sp = os.path.join(tp, sub)
            if not os.path.isdir(sp) or sub.startswith('.'):
                continue
            total = sum(1 for r,d,f in os.walk(sp) for fn in f 
                       if os.path.splitext(fn)[1].lower() in video_exts)
            if total >= 1:
                folders.append({
                    "category": top,
                    "name": sub,
                    "path": sp,
                    "videos": total,
                    "done": sub in ALREADY_DONE,
                })
    return folders

def main():
    folders = collect_folders()
    todo = [f for f in folders if not f["done"]]

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
    # 重新收集
    folders = collect_folders()
    todo = [f for f in folders if not f["done"]]
    
    print(f"总文件夹: {len(folders)}")
    print(f"已完成: {len(folders) - len(todo)}")
    print(f"待执行: {len(todo)}")
    print()
    
    results = []
    errors = []
    
    for i, f in enumerate(todo):
        print(f"\n[{i+1}/{len(todo)}] [{f['category']}] {f['name']} ({f['videos']} vids)")
        t0 = time.time()
        try:
            r = run_pipeline(f["path"], execute=True)
            elapsed = time.time() - t0
            results.append({
                "name": f["name"],
                "category": f["category"],
                "folder_type": r.get("folder_type", ""),
                "struct_ops": r.get("struct_ops", 0),
                "rename_changed": r.get("rename_changed", 0),
                "elapsed": round(elapsed, 1),
                "status": "ok",
            })
            print(f"  OK {r.get('folder_type','')} ({elapsed:.1f}s)")
        except Exception as e:
            elapsed = time.time() - t0
            tb = traceback.format_exc()
            errors.append({
                "name": f["name"],
                "category": f["category"],
                "error": str(e),
                "traceback": tb,
            })
            print(f"  ERR: {str(e)[:80]} ({elapsed:.1f}s)")
    
    # 汇总
    print(f"\n{'='*60}")
    print(f"全量整理完成")
    print(f"成功: {len(results)}, 失败: {len(errors)}")
    
    if errors:
        print(f"\n失败列表:")
        for e in errors:
            print(f"  [{e['category']}] {e['name']}: {e['error'][:60]}")
    
    # 保存结果
    report = {"results": results, "errors": errors, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open("_batch_report.json", "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: _batch_report.json")

if __name__ == "__main__":
    main()
