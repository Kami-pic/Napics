"""豆瓣 API v2 接口测试脚本"""
import json
import douban_api_v2


def test_movie_hot():
    """测试热门电影"""
    print("\n=== 热门电影 ===")
    items = douban_api_v2.movie_hot(start=0, count=5)
    assert len(items) > 0, "热门电影返回为空"
    for item in items:
        assert item.get("douban_id"), f"缺少 douban_id: {item.get('title')}"
        assert item.get("title"), "缺少 title"
        assert item.get("poster_url"), f"缺少 poster_url: {item.get('title')}"
        print(f"  ✓ {item['title']} ({item.get('year')}) 评分:{item.get('rating')} ID:{item['douban_id']}")
    print(f"  共 {len(items)} 条，全部有 douban_id + title + poster_url")


def test_movie_showing():
    """测试正在热映"""
    print("\n=== 正在热映 ===")
    items = douban_api_v2.movie_showing(start=0, count=5)
    assert len(items) > 0, "正在热映返回为空"
    for item in items:
        assert item.get("title"), "缺少 title"
        print(f"  ✓ {item['title']} ({item.get('year')}) 评分:{item.get('rating')}")
    print(f"  共 {len(items)} 条")


def test_movie_top250():
    """测试 TOP250"""
    print("\n=== 电影 TOP250 ===")
    items = douban_api_v2.movie_top250(start=0, count=5)
    assert len(items) > 0, "TOP250 返回为空"
    for item in items:
        assert item.get("rating", 0) > 0, f"TOP250 评分应该 > 0: {item.get('title')}"
        print(f"  ✓ {item['title']} ({item.get('year')}) 评分:{item.get('rating')}")
    print(f"  共 {len(items)} 条，全部有评分")


def test_tv_hot():
    """测试热门剧集"""
    print("\n=== 热门剧集 ===")
    items = douban_api_v2.tv_hot(start=0, count=5)
    assert len(items) > 0, "热门剧集返回为空"
    for item in items:
        print(f"  ✓ {item['title']} ({item.get('year')}) 评分:{item.get('rating')}")
    print(f"  共 {len(items)} 条")


def test_tv_animation():
    """测试热门动画"""
    print("\n=== 热门动画 ===")
    items = douban_api_v2.tv_animation(start=0, count=5)
    assert len(items) > 0, "热门动画返回为空"
    for item in items:
        print(f"  ✓ {item['title']} ({item.get('year')}) 评分:{item.get('rating')}")
    print(f"  共 {len(items)} 条")


def test_tv_weekly_chinese():
    """测试华语口碑周榜"""
    print("\n=== 华语口碑周榜 ===")
    items = douban_api_v2.tv_weekly_chinese(start=0, count=5)
    assert len(items) > 0, "华语周榜返回为空"
    for item in items:
        print(f"  ✓ {item['title']} ({item.get('year')}) 评分:{item.get('rating')}")
    print(f"  共 {len(items)} 条")


def test_tv_weekly_global():
    """测试全球口碑周榜"""
    print("\n=== 全球口碑周榜 ===")
    items = douban_api_v2.tv_weekly_global(start=0, count=5)
    assert len(items) > 0, "全球周榜返回为空"
    for item in items:
        print(f"  ✓ {item['title']} ({item.get('year')}) 评分:{item.get('rating')}")
    print(f"  共 {len(items)} 条")


def test_movie_explore():
    """测试电影探索（按标签筛选）"""
    print("\n=== 电影探索（剧情+高分优先）===")
    items = douban_api_v2.movie_explore(tags="剧情", sort="S", start=0, count=5)
    assert len(items) > 0, "电影探索返回为空"
    for item in items:
        print(f"  ✓ {item['title']} ({item.get('year')}) 评分:{item.get('rating')} 类型:{item.get('genres')}")
    print(f"  共 {len(items)} 条")


def test_tv_explore():
    """测试剧集探索"""
    print("\n=== 剧集探索（热度排序）===")
    items = douban_api_v2.tv_explore(sort="R", start=0, count=5)
    assert len(items) > 0, "剧集探索返回为空"
    for item in items:
        print(f"  ✓ {item['title']} ({item.get('year')}) 评分:{item.get('rating')}")
    print(f"  共 {len(items)} 条")


def test_search():
    """测试搜索"""
    print("\n=== 搜索：流浪地球 ===")
    items = douban_api_v2.search("流浪地球", count=5)
    assert len(items) > 0, "搜索返回为空"
    found_target = False
    for item in items:
        title = item.get("title", "")
        print(f"  ✓ {title} ({item.get('year')}) 评分:{item.get('rating')} ID:{item.get('douban_id')}")
        if "流浪地球" in title:
            found_target = True
    assert found_target, "搜索结果中没有找到'流浪地球'"
    print(f"  共 {len(items)} 条，包含目标影片")


def test_movie_detail():
    """测试电影详情（用肖申克的救赎 douban_id=1292052）"""
    print("\n=== 电影详情：肖申克的救赎 ===")
    detail = douban_api_v2.movie_detail("1292052")
    assert detail is not None, "电影详情返回为空"
    assert detail.get("title"), "缺少 title"
    assert detail.get("douban_id") == "1292052", f"douban_id 不匹配: {detail.get('douban_id')}"
    assert detail.get("rating", 0) > 8, f"肖申克评分应该 > 8: {detail.get('rating')}"
    assert detail.get("overview"), "缺少 overview"
    assert detail.get("directors"), "缺少 directors"
    assert detail.get("actors"), "缺少 actors"
    assert detail.get("poster_url"), "缺少 poster_url"
    print(f"  标题: {detail['title']}")
    print(f"  原名: {detail.get('original_title')}")
    print(f"  年份: {detail.get('year')}")
    print(f"  评分: {detail.get('rating')}")
    print(f"  类型: {detail.get('genres')}")
    print(f"  导演: {detail.get('directors')}")
    print(f"  演员: {detail.get('actors')}")
    print(f"  时长: {detail.get('runtime')} 分钟")
    print(f"  国家: {detail.get('countries')}")
    print(f"  简介: {detail.get('overview', '')[:60]}...")
    print(f"  海报: {detail.get('poster_url', '')[:60]}...")
    print("  ✓ 所有关键字段完整")


def test_tv_detail():
    """测试剧集详情（用权力的游戏 douban_id=26584183）"""
    print("\n=== 剧集详情：权力的游戏 ===")
    detail = douban_api_v2.tv_detail("26584183")
    assert detail is not None, "剧集详情返回为空"
    assert detail.get("title"), "缺少 title"
    print(f"  标题: {detail['title']}")
    print(f"  评分: {detail.get('rating')}")
    print(f"  集数: {detail.get('episode_count')}")
    print(f"  季数: {detail.get('seasons_count')}")
    print(f"  类型: {detail.get('genres')}")
    print("  ✓ 剧集详情完整")


def test_cache():
    """测试缓存：第二次调用应该走缓存（无延迟）"""
    import time
    print("\n=== 缓存测试 ===")
    # 第一次已经在上面的测试中调用过了，缓存应该已存在
    t0 = time.time()
    items = douban_api_v2.movie_hot(start=0, count=5)
    elapsed = time.time() - t0
    assert len(items) > 0, "缓存读取失败"
    assert elapsed < 1.0, f"缓存读取耗时 {elapsed:.2f}s，应该 < 1s（说明没走缓存）"
    print(f"  ✓ 缓存命中，耗时 {elapsed:.3f}s（< 1s）")


def test_detail_vs_old_client():
    """对比 API v2 详情 vs 旧版爬网页详情"""
    print("\n=== 对比：API v2 vs 旧版网页爬取 ===")
    import douban_client
    
    subject_id = "1292052"  # 肖申克的救赎
    
    # API v2
    v2 = douban_api_v2.movie_detail(subject_id)
    # 旧版
    old = douban_client.get_detail(subject_id)
    
    print(f"  API v2 字段数: {len(v2) if v2 else 0}")
    print(f"  旧版字段数:   {len(old) if old else 0}")
    
    if v2 and old:
        # 对比关键字段
        for field in ["title", "year", "rating", "overview", "director", "genres"]:
            v2_val = v2.get(field) or v2.get("directors", [""])[0] if field == "director" else v2.get(field)
            old_val = old.get(field)
            match = "✓" if v2_val and old_val else "⚠"
            print(f"  {match} {field}: v2={str(v2_val)[:40]} | old={str(old_val)[:40]}")
        
        # v2 独有字段
        v2_extras = [k for k in v2 if k not in (old or {})]
        print(f"  API v2 独有字段: {v2_extras}")
    print("  ✓ 对比完成")


if __name__ == "__main__":
    tests = [
        test_movie_hot,
        test_movie_showing,
        test_movie_top250,
        test_tv_hot,
        test_tv_animation,
        test_tv_weekly_chinese,
        test_tv_weekly_global,
        test_movie_explore,
        test_tv_explore,
        test_search,
        test_movie_detail,
        test_tv_detail,
        test_cache,
        test_detail_vs_old_client,
    ]
    
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n  ✗ {test.__name__} 失败: {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"测试结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 个")
