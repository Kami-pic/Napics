import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

sys.stdout = open("black_lagoon_report.txt", "w", encoding="utf-8")

import config_manager
import organizer
import scraper
from tmdb_client import TMDBClient

def main():
    config_m = config_manager.ConfigManager()
    api_key = config_m.config.tmdb_api_key
    proxy = config_m.config.http_proxy or ''
    client = TMDBClient(api_key, proxy=proxy) if api_key else None

    sandbox_real = os.path.join(os.path.dirname(__file__), "sandbox_real")

    # 找到包含黑礁的目录
    target_dir = None
    for root, dirs, files in os.walk(sandbox_real):
        bname = os.path.basename(root).lower()
        if "black lagoon" in bname or "黑礁" in bname:
            target_dir = root
            break

    if not target_dir:
        print("在镜像中没有找到叫 Black Lagoon 或 黑礁 的顶层目录。请检查它有没有被包在什么上层分类夹中！")
        return

    print("================================")
    print(f"🎯 真实源结构: {os.path.relpath(target_dir, sandbox_real)}")
    print("================================")
    for r, d, f in os.walk(target_dir):
        # 美观一些输出
        depth = os.path.relpath(r, target_dir).count(os.sep)
        if os.path.relpath(r, target_dir) == ".":
            pass
        else:
            print("  " * depth + f"[{os.path.basename(r)}/]")
        for file in f:
            print("  " * (depth + 1) + str(file))

    print("\n================================")
    print("✨ 一键整理流水线 Dry-Run")
    print("================================")
    info = organizer.classify_folder(target_dir)
    try:
        result = scraper.scrape_folder(target_dir, client, force=True, folder_type=info.get("type", "tv"), dry_run=True)
        plan = result.get("plan", [])
        
        for item in plan:
             rel_orig = os.path.relpath(item['original_path'], target_dir)
             mapped = item.get("mapped")
             if mapped:
                  s = mapped.get("season", 0)
                  e = mapped.get("episode", 0)
                  target_s = f"Season {s:02d}"
                  print(f"✅ {rel_orig}\n     ----(重塑)----> [{target_s}] / [S{s:02d}E{e:02d}] {item['original_filename']}")
             else:
                  print(f"⚠️ 抛弃无管: {rel_orig} (原因: {item.get('skip_reason')})")
    except Exception as e:
        print(f"❌ 分析出错: {e}")

if __name__ == "__main__":
    main()
