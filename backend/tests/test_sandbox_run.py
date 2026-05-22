import os
import sys

# 保证本目录的基准路径没问题
sys.path.insert(0, os.path.dirname(__file__))

import config_manager
import organizer
import scraper
from tmdb_client import TMDBClient, parse_filename

def run_test():
    config_m = config_manager.ConfigManager()
    api_key = config_m.config.tmdb_api_key
    proxy = config_m.config.http_proxy or ''
    # 如果没配 tmdb，没法刮削会直接退出，这里尽量带着真实的客户端
    client = TMDBClient(api_key, proxy=proxy) if api_key else None

    sandbox_base = os.path.join(os.path.dirname(__file__), "test_sandbox", "视频")
    
    # 我们遍历所有的 test 目录
    scenarios = [
        ("场景 1 (电影洗版区)", os.path.join(sandbox_base, "电影", "The Matrix (1999)")),
        ("场景 2 (夹带散兵的剧集)", os.path.join(sandbox_base, "剧集", "Breaking Bad")),
        ("场景 3 (名字地狱级乱写的动漫)", os.path.join(sandbox_base, "动画番", "Eighty Six")),
        ("场景 4 (嵌套结构 + 大乱炖灾难现场)", os.path.join(sandbox_base, "下载区", "[XXX广告组首发] 混杂乱炖不知名影视大包")),
        ("场景 5 (缺失标准化的季目录包裹)", os.path.join(sandbox_base, "剧集", "The Boys")),
        ("场景 6 (全损命名的裸奔下载源)", os.path.join(sandbox_base, "下载区", " Breaking.Bad.S01E03.1080p.WEB-DL")),
        ("场景 7 (重度嵌套/OVA/附带不相关资料的高玩库-黑礁)", os.path.join(sandbox_base, "动画番", "Black Lagoon")),
        ("场景 8 (重度嵌套外加凌乱结构的妖精的旋律)", os.path.join(sandbox_base, "动画番", "Elfen Lied"))
    ]
    
    for name, path in scenarios:
        if not os.path.exists(path):
            continue
            
        print("\n" + "=" * 80)
        print(f"🔥🔥🔥 {name} 测试开始")
        print(f"路径: {path}")
        print("=" * 80)

        # 列出这所有的视频文件给 parse_filename 测试
        vexts = {".mp4", ".mkv", ".avi", ".rmvb", ".flv", ".ts", ".m4v"}
        vids = []
        for root, dirs, files in os.walk(path):
            for f in files:
                if os.path.splitext(f)[1].lower() in vexts:
                    vids.append(os.path.join(root, f))
                    
        print("\n🔍 【1. 解析与重命名测试 (提取结果)】:")
        for v in vids:
            rel_vp = os.path.relpath(v, path)
            r = parse_filename(os.path.basename(v))
            print(f"   [原路径] {rel_vp}")
            print(f"       => 提取 S{r.get('season')}E{r.get('episode')} \t| 剧名提取: [{r.get('clean_name')}]")

        print("\n📂 【2. 自动分类分析 (分类结果)】:")
        # 因为沙盘放在了 test_sandbox 并不是真正的 NAS 根目录，这里不用 category_hint 走纯推测
        info = organizer.classify_folder(path)
        print(f"   推测类型: {info.get('type')} (tv/movie/mix)")

        print("\n🎯 【3. 刮削搜索 & 标准结构演练 (Dry-Run)】:")
        try:
            result = scraper.scrape_folder(path, client, force=True, folder_type=info.get("type", "tv"), dry_run=True)
            tmdb_match = result.get("tmdb_match", {})
            plan = result.get("plan", [])
            summary = result.get("summary", {})

            # 模拟替换检测（新旧比较），整理管线里通常在这里检测冲突或归位
            print(f"   ► TMDB匹配目标 => {tmdb_match.get('title', '毫无匹配')} (ID: {tmdb_match.get('tmdb_id')})")
            print(f"   ► 需创建季度目录 => {summary.get('seasons_to_create', [])}")

            print("   ► 计划操作清单:")
            for item in plan:
                mapped = item.get("mapped")
                if mapped:
                    target_season = f"Season {mapped['season']:02d}"
                    print(f"     ✅ 将整理 => {item['original_filename']} --改名为--> S{mapped['season']:02d}E{mapped['episode']:02d} 并放到 {target_season}")
                else:
                    print(f"     ⚠️ 跳过文件 => {item['original_filename']} (原因: {item.get('skip_reason', '解析失败')})")
        except Exception as e:
            print(f"   ❌ 流水线报错: {e}")

if __name__ == "__main__":
    run_test()
