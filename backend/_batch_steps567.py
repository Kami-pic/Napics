"""全量执行第5-7步：刮削 → 标准名生成 → 影子名写入
前提：第2-4步已执行完毕（结构已归位）。
"""
import sys, os, time, json, traceback
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

NAS = r"\\DS218play\share\视频"
SKIP_DIRS = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}


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


def run_steps567(folder_path, execute=True):
    """第5步刮削 → 第6步标准名 → 第7步影子名"""
    name = os.path.basename(folder_path)

    # 先分析获取 folder_type（只读，不改文件）
    report = analyzer.analyze_folder(folder_path, library)
    ft = report.get("folder_type", "")

    # === 第5步：刮削 ===
    scrape_status = "skipped"
    scrape_children = 0
    if execute:
        try:
            sr = scraper.scrape_folder(folder_path, client, force=True, folder_type=ft)
            scrape_status = sr.get("self", {}).get("status", "unknown")
            scrape_children = len(sr.get("children", []))
        except Exception as e:
            scrape_status = f"error: {str(e)[:60]}"
    print(f"  刮削: {scrape_status}, 子项: {scrape_children}")

    # === 第6步：标准名生成（dry_run=True，只生成不改名）===
    rename_result = organizer.rename_videos_in_folder(
        folder_path, client, dry_run=True, library_data=library, folder_type=ft
    )
    changed = [r for r in rename_result if not r.get("unchanged")]
    total_videos = [r for r in rename_result if not r.get("is_folder")]
    print(f"  标准名: {len(total_videos)} 视频, {len(changed)} 需改名")

    # === 第7步：影子名写入 ===
    shadow_count = 0
    shadow_failed = 0
    if execute:
        for r in rename_result:
            fp = r.get("old_path", "")
            shadow = r.get("shadow_name", "")
            if not fp or not shadow:
                continue
            # 文件夹级的影子名也写入（用 file_path = folder_path）
            if r.get("is_folder") and not r.get("is_subfolder"):
                # 父文件夹影子名 — 不写 media_library（library 里没有文件夹条目）
                continue
            if r.get("is_subfolder"):
                continue
            ok = shadow_m.auto_fill(fp, shadow, source="parsed",
                                    organize_status="ok" if scrape_status not in ("error",) else "scrape_failed")
            if ok:
                shadow_count += 1
            else:
                shadow_failed += 1
    print(f"  影子名: 写入 {shadow_count}, 跳过 {shadow_failed}")

    # 打印前几个影子名样例
    samples = [r for r in rename_result if not r.get("is_folder") and r.get("shadow_name")][:3]
    for s in samples:
        print(f"    {os.path.basename(s['old_path'])[:35]} → {s['shadow_name'][:40]}")

    return {
        "folder_type": ft,
        "scrape_status": scrape_status,
        "scrape_children": scrape_children,
        "videos": len(total_videos),
        "rename_changed": len(changed),
        "shadow_written": shadow_count,
        "shadow_skipped": shadow_failed,
    }


def main():
    folders = collect_folders()
    print(f"总文件夹: {len(folders)}\n")

    results = []
    errors = []

    for i, f in enumerate(folders):
        print(f"[{i+1}/{len(folders)}] [{f['category']}] {f['name']} ({f['videos']} vids)")
        t0 = time.time()
        try:
            r = run_steps567(f["path"], execute=True)
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
    print(f"第5-7步全量完成")
    print(f"成功: {len(results)}, 失败: {len(errors)}")

    type_counts = {}
    total_videos = 0
    total_shadow = 0
    total_scrape_ok = 0
    for r in results:
        ft = r.get("folder_type", "unknown")
        type_counts[ft] = type_counts.get(ft, 0) + 1
        total_videos += r.get("videos", 0)
        total_shadow += r.get("shadow_written", 0)
        if "error" not in str(r.get("scrape_status", "")):
            total_scrape_ok += 1

    print(f"\n类型分布: {json.dumps(type_counts, ensure_ascii=False)}")
    print(f"总视频: {total_videos}")
    print(f"刮削成功: {total_scrape_ok}/{len(results)}")
    print(f"影子名写入: {total_shadow}")

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
            "total_videos": total_videos,
            "total_scrape_ok": total_scrape_ok,
            "total_shadow": total_shadow,
        },
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open("_batch_steps567_report.json", "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: _batch_steps567_report.json")


if __name__ == "__main__":
    main()
