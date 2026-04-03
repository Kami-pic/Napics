"""V3 流水线 dry_run 测试：钢之炼金术师FA（纯数字文件名）+ 混沌武士（乱码文件名）"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

import config_manager
import analyzer
import scraper
import organizer
from tmdb_client import TMDBClient, parse_filename

config_m = config_manager.ConfigManager()
api_key = config_m.config.tmdb_api_key
proxy = config_m.config.http_proxy or ''
client = TMDBClient(api_key, proxy=proxy) if api_key else None

base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""

def test_folder(name, path):
    print("=" * 70)
    print(f"测试: {name}")
    print(f"路径: {path}")
    print("=" * 70)

    # 1. 先测几个文件名的 parse_filename
    vexts = {".mp4", ".mkv", ".avi", ".rmvb", ".flv", ".ts", ".m4v"}
    vids = sorted([f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and os.path.splitext(f)[1].lower() in vexts])
    print(f"\n视频数: {len(vids)}")
    print("\nparse_filename 测试（前5个）:")
    for v in vids[:5]:
        r = parse_filename(v)
        print(f"  {v}")
        print(f"    → season={r['season']}, episode={r['episode']}, absolute={r['absolute_episode']}, clean={r['clean_name']}")

    # 2. classify_folder
    category_hint = organizer.infer_category_tag("动画番")
    info = organizer.classify_folder(path, category_hint=category_hint)
    print(f"\nclassify: type={info.get('type')}, category_hint={category_hint}")

    # 3. scrape_folder dry_run
    print("\n--- scrape_folder dry_run=True ---")
    try:
        result = scraper.scrape_folder(path, client, force=True, folder_type=info.get("type", "tv"), dry_run=True)
        tmdb_match = result.get("tmdb_match", {})
        plan = result.get("plan", [])
        summary = result.get("summary", {})

        print(f"TMDB 匹配: {tmdb_match.get('title', 'N/A')} (id={tmdb_match.get('tmdb_id', 0)}, source={tmdb_match.get('match_source', 'N/A')})")
        print(f"总视频: {summary.get('total_videos', 0)}, 将处理: {summary.get('will_process', 0)}, 跳过: {summary.get('will_skip', 0)}")
        print(f"季目录: {summary.get('seasons_to_create', [])}")

        # 显示前 8 个 plan item
        print(f"\nPlan 详情（前8个）:")
        for item in plan[:8]:
            mapped = item.get("mapped")
            if mapped:
                print(f"  {item['original_filename']} → S{mapped['season']:02d}E{mapped['episode']:02d} [{item['parsed']['method']}] shadow={item.get('target_shadow_name','')}")
            else:
                print(f"  {item['original_filename']} → SKIP: {item.get('skip_reason', '?')} [{item['parsed']['method']}]")

        # 显示跳过的
        skipped = [i for i in plan if i.get("skip_reason")]
        if skipped:
            print(f"\n跳过的 ({len(skipped)} 个):")
            for s in skipped[:5]:
                print(f"  {s['original_filename']}: {s['skip_reason']}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()

    print()

# 测试 1: 钢之炼金术师FA — 纯数字文件名（02.rmvb ~ 63.rmvb）
test_folder("钢之炼金术师FA（纯数字文件名，63集）",
            os.path.join(base, "动画番", "钢之炼金术师FA"))

# 测试 2: 混沌武士 — 乱码文件夹名 + 方括号字幕组文件名
test_folder("混沌武士（乱码文件夹名+字幕组格式）",
            os.path.join(base, "动画番", "混沌武士  Samurai Champloo (BD 720P x264 10bit AAC)"))
