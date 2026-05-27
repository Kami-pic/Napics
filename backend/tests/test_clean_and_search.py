"""清洗函数 + 搜索策略的回归测试
运行: python test_clean_and_search.py
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
from analyzer import _clean_filename_for_folder, _extract_cd_group_key


def test_clean_filename():
    """清洗函数回归测试"""
    cases = [
        # (输入, 期望输出)
        # 广告清洗
        ("黑客帝国.1080p.BD中英双字无水印[66影视www.66Ys.Co].mkv", "黑客帝国"),
        ("星球大战前传1幽灵的威胁BD双语双字修复版[电影天堂www.dy2018.com].mkv", "星球大战前传1幽灵的威胁"),
        ("影视帝国(bbs.cnxp.com).触不到的恋人.cd1.rmvb", "触不到的恋人"),
        ("【更多美剧请去www.dy131.com】冰与火之歌：权力的游戏第一季HD中英双字1280高清01.rmvb", "冰与火之歌：权力的游戏01"),
        # 质量标签
        ("权力的游戏.Game.of.Thrones.S05E01.中英字幕.WEB-HR.AAC.1024X576.x264.mp4", "权力的游戏 Game of Thrones S05E01"),
        # CD 分片
        ("阿甘正传CD1.rmvb", "阿甘正传"),
        ("IF ONLY.CD2.rm", "IF ONLY"),
        # 日文引号
        ("命运之夜 天之杯Ⅰ：恶兆之花 劇場版「Fatestay night [Heaven's Feel] Ⅰ. presage flower」(2017) 1080p.mkv",
         "命运之夜 天之杯Ⅰ：恶兆之花 (2017)"),
        # 媒体形式标签
        ("魁拔—殊途.tmp", "魁拔—殊途"),
        # 纯英文
        ("The.Matrix.1999.1080p.BluRay.x264-SPARKS.mkv", "The Matrix 1999"),
        ("Inception.2010.2160p.UHD.BluRay.x265-TERMINAL.mkv", "Inception 2010"),
        ("Breaking.Bad.S01E01.720p.BluRay.x264-DEMAND.mkv", "Breaking Bad S01E01"),
        # 不应该被破坏的
        ("珍珠港 Pearl Harbor (2001).rmvb", "珍珠港 Pearl Harbor (2001)"),
        ("永远之久远 第一章 泡沫的花瓣 Towa no Quon 1 The Ephemeral Petals (2011).rmvb",
         "永远之久远 第一章 泡沫的花瓣 Towa no Quon 1 The Ephemeral Petals (2011)"),
    ]
    
    passed = 0
    failed = 0
    for filename, expected in cases:
        result = _clean_filename_for_folder(filename)
        if result == expected:
            passed += 1
            print(f"  ✓ {filename[:50]}")
        else:
            failed += 1
            print(f"  ✗ {filename[:50]}")
            print(f"    期望: {expected}")
            print(f"    实际: {result}")
    
    print(f"\n清洗测试: {passed} 通过, {failed} 失败")
    return failed == 0


def test_cd_grouping():
    """CD 分组回归测试"""
    cases = [
        ("阿甘正传CD1.rmvb", "阿甘正传CD2.rmvb", True),
        ("IF ONLY.CD1.rm", "IF ONLY.CD2.rm", True),
        ("珍珠港.rmvb", "阿甘正传CD1.rmvb", False),
        ("阿甘正传.rmvb", "阿甘正传CD2.rmvb", False),
    ]
    
    passed = 0
    failed = 0
    for f1, f2, should_match in cases:
        k1 = _extract_cd_group_key(f1)
        k2 = _extract_cd_group_key(f2)
        matched = k1 is not None and k2 is not None and k1 == k2
        if matched == should_match:
            passed += 1
            print(f"  ✓ {f1} + {f2} → {'同组' if matched else '不同组'}")
        else:
            failed += 1
            print(f"  ✗ {f1} + {f2} → 期望{'同组' if should_match else '不同组'}，实际{'同组' if matched else '不同组'}")
    
    print(f"\nCD分组测试: {passed} 通过, {failed} 失败")
    return failed == 0


def test_search_strategy():
    """搜索策略回归测试（需要 TMDB API 和网络）"""
    try:
        import tmdb_client as tc
        import config_manager
        config_m = config_manager.ConfigManager()
        if not config_m.config.tmdb_api_key:
            print("\n搜索测试: 跳过（无 TMDB API key）")
            return True
        client = tc.TMDBClient(config_m.config.tmdb_api_key, proxy=config_m.config.http_proxy or '')
    except Exception as e:
        print(f"\n搜索测试: 跳过（{e}）")
        return True
    
    # (搜索词, 期望匹配关键词)
    cases = [
        ("切尔诺贝利", "Chernobyl"),
        ("权力的游戏", "Game of Thrones"),
        ("哥斯拉 决战之都", "Godzilla"),
        ("灵探特莱丝 Trese", "Trese"),
        ("The Matrix 1999", "Matrix"),
        ("Inception 2010", "Inception"),
        ("Breaking Bad S01E01", "Breaking Bad"),
    ]
    
    passed = 0
    failed = 0
    for query, expected in cases:
        result = client.scrape_by_filename(query)
        title = (result.title or "") + " " + (result.original_title or "")
        if expected.lower() in title.lower():
            passed += 1
            print(f"  ✓ {query} → {result.title}")
        else:
            failed += 1
            print(f"  ✗ {query} → {result.title or 'NOT_FOUND'} (期望含 {expected})")
    
    print(f"\n搜索测试: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    print("=" * 50)
    print("清洗函数测试")
    print("=" * 50)
    ok1 = test_clean_filename()
    
    print("\n" + "=" * 50)
    print("CD 分组测试")
    print("=" * 50)
    ok2 = test_cd_grouping()
    
    print("\n" + "=" * 50)
    print("搜索策略测试")
    print("=" * 50)
    ok3 = test_search_strategy()
    
    print("\n" + "=" * 50)
    all_ok = ok1 and ok2 and ok3
    print(f"总结: {'全部通过 ✓' if all_ok else '有失败 ✗'}")
