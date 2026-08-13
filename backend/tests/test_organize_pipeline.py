"""整理流水线回归测试 — 对真实文件夹做 dry_run 验证
运行: python test_organize_pipeline.py
每次改算法后必须跑这个测试确保不退化
"""
import sys, os, json, zipfile
sys.path.insert(0, os.path.dirname(__file__))

import analyzer
import organizer
import scraper
import tmdb_client
import config_manager
from shadow_name_manager import ShadowNameManager

config_m = config_manager.ConfigManager()
library = config_m.load_library()
client = tmdb_client.TMDBClient(config_m.config.tmdb_api_key, proxy=config_m.config.http_proxy or '')

NAS = r"\\NAS\share\视频"

# 测试用例：(路径, 期望类型, 期望结构操作数, 期望刮削状态, 期望标准名关键词)
TEST_CASES = [
    # tv 类型
    (NAS + r"\电视剧\切尔诺贝利S1", "tv", 0, "ok", "Chernobyl"),
    (NAS + r"\电视剧\方子传TV版", "tv", 0, "ok", "Servant"),
    (NAS + r"\电视剧\龙之家族第一季", "tv", 0, "ok", "House of the Dragon"),
    (NAS + r"\动画番\灵探特莱丝.Trese.S01", "tv", 0, "ok", "Trese"),
    (NAS + r"\动画番\银翼杀手：黑莲花", "tv", 0, "ok", "Blade Runner"),
    (NAS + r"\动画番\特别的她", "tv", 0, "ok", "FLCL"),
    # series_collection 类型
    (NAS + r"\动画电影\来自深渊剧场版三部曲", "series_collection", 3, None, None),
    (NAS + r"\动画电影\壳中少女 Mardock Scramble", "series_collection", 0, None, "Mardock"),
    (NAS + r"\动画电影\哥斯拉动画电影", "series_collection", 0, None, "Godzilla"),
    # 第3轮新增
    (NAS + r"\电视剧\better call saul s5", "tv", 0, "ok", "Better Call Saul"),
    (NAS + r"\电视剧\指环王：力量之戒", "tv", 0, "ok", "Rings of Power"),
    (NAS + r"\动画电影\福音战士新剧场版 Evangelion 三部曲", "series_collection", 0, None, "Evangelion"),
    # 经典电影（最复杂：mixed + CD分片 + 多种子文件夹）
    (NAS + r"\电影\经典电影之新世代诠释 Reframed Next Gen Narratives", "mixed", None, None, None),
    # 随机测试新增
    (NAS + r"\电视剧\辐射 Fallout", "tv", 0, "ok", "Fallout"),
    (NAS + r"\动画番\赛博朋克：边缘行者", "tv", 0, "ok", "Cyberpunk"),
    (NAS + r"\电视剧\兄弟连", "tv", 0, "ok", "Band of Brothers"),
    (NAS + r"\电视剧\守望者S1", "tv", 0, "ok", "Watchmen"),
    # 冰与火之歌（最难：父目录名搜不到，需要从子目录文件名提取英文）
    (NAS + r"\电视剧\冰与火之歌1-8季", "tv", 0, None, "Game of Thrones"),  # 季目录标准名含 Game of Thrones
]


def restore_old_scrape(folder_path):
    """从 .old_scrape.zip 恢复旧刮削"""
    zp = os.path.join(folder_path, ".old_scrape.zip")
    if os.path.exists(zp):
        with zipfile.ZipFile(zp, 'r') as zf:
            zf.extractall(folder_path)
        os.remove(zp)
        return True
    # 也恢复子文件夹
    restored = False
    for d in os.listdir(folder_path):
        dp = os.path.join(folder_path, d)
        if os.path.isdir(dp):
            szp = os.path.join(dp, ".old_scrape.zip")
            if os.path.exists(szp):
                with zipfile.ZipFile(szp, 'r') as zf:
                    zf.extractall(dp)
                os.remove(szp)
                restored = True
    return restored


def run_test(path, expected_type, expected_struct_ops, expected_scrape, expected_keyword):
    """对单个文件夹做完整流水线测试"""
    name = os.path.basename(path)
    if not os.path.isdir(path):
        return False, f"路径不存在: {path}"
    
    errors = []
    
    # 先恢复旧刮削（如果之前被打包了）
    restore_old_scrape(path)
    
    # 第1步：备份旧刮削（删除）
    from _organize_pipeline import archive_old_scrape
    archive_old_scrape(path, delete_after=True)
    
    # 第2步：分析
    report = analyzer.analyze_folder(path, library)
    ft = report.get("folder_type", "")
    struct_ops = report.get("structure_ops", [])
    
    if expected_type is not None and ft != expected_type:
        errors.append(f"类型: 期望 {expected_type}, 实际 {ft}")
    
    if expected_struct_ops is not None and len(struct_ops) != expected_struct_ops:
        errors.append(f"结构操作: 期望 {expected_struct_ops}, 实际 {len(struct_ops)}")
    
    # 第3步：刮削（只对末端文件夹测试）
    if expected_scrape is not None:
        scrape_result = scraper.scrape_folder(path, client, force=True)
        self_status = scrape_result.get("self", {}).get("status", "")
        if self_status != expected_scrape:
            errors.append(f"刮削: 期望 {expected_scrape}, 实际 {self_status}")
    
    # 第4步：标准名检查
    if expected_keyword:
        rename_result = organizer.rename_videos_in_folder(path, client, dry_run=True, library_data=library)
        all_shadows = [r.get("shadow_name", "") for r in rename_result]
        has_keyword = any(expected_keyword.lower() in s.lower() for s in all_shadows if s)
        if not has_keyword:
            shadows_str = "; ".join(s[:30] for s in all_shadows[:5] if s)
            errors.append(f"标准名缺少 '{expected_keyword}': {shadows_str}")
    
    # 恢复旧刮削（测试完恢复原状）
    restore_old_scrape(path)
    
    if errors:
        return False, "; ".join(errors)
    return True, "OK"


def run_all_tests():
    """运行所有测试"""
    passed = 0
    failed = 0
    
    for path, exp_type, exp_ops, exp_scrape, exp_kw in TEST_CASES:
        name = os.path.basename(path)
        ok, msg = run_test(path, exp_type, exp_ops, exp_scrape, exp_kw)
        if ok:
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name}: {msg}")
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    print("=" * 50)
    print("整理流水线回归测试")
    print("=" * 50)
    ok = run_all_tests()
    if not ok:
        sys.exit(1)
