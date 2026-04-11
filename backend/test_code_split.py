"""
代码拆分回归测试 — 验证所有拆分模块的导入兼容性和核心功能
覆盖：nfo_handler / poster_downloader / renamer / structure_organizer
      routes/media_info / routes/poster / routes/relocate / routes/analyze
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
# Windows 编码修复
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import tempfile
import shutil

passed = 0
failed = 0

def ok(name):
    global passed
    passed += 1
    print(f"  ✓ {name}")

def fail(name, err):
    global failed
    failed += 1
    print(f"  ✗ {name}: {err}")

def test(name, fn):
    try:
        fn()
        ok(name)
    except Exception as e:
        fail(name, e)


print("=" * 60)
print("后端拆分回归测试")
print("=" * 60)

# ══════════════════════════════════════════
# 1. nfo_handler — NFO 读写
# ══════════════════════════════════════════
print("\n── nfo_handler ──")

def test_nfo_handler_import():
    from nfo_handler import (
        read_nfo, read_video_nfo, write_movie_nfo, write_tvshow_nfo,
        write_season_nfo, write_episode_nfo, _text, _add, _write_xml,
        _is_category_folder, write_movie_nfo_for_video,
    )
test("导入所有函数", test_nfo_handler_import)

def test_nfo_write_read():
    """写入 movie.nfo 再读回来，验证数据一致"""
    from nfo_handler import write_movie_nfo, read_nfo
    from tmdb_client import ScrapeResult
    tmp = tempfile.mkdtemp()
    try:
        scrape = ScrapeResult(
            tmdb_id=550, media_type="movie", title="搏击俱乐部",
            original_title="Fight Club", english_title="Fight Club",
            year="1999", rating=8.4, genres=["剧情", "惊悚"],
            director="大卫·芬奇", cast=["布拉德·皮特", "爱德华·诺顿"],
        )
        write_movie_nfo(tmp, scrape)
        assert os.path.exists(os.path.join(tmp, "movie.nfo"))
        data = read_nfo(tmp)
        assert data is not None
        assert data["title"] == "搏击俱乐部"
        assert data["tmdb_id"] == 550
        assert data["year"] == "1999"
        assert "剧情" in data["genres"]
    finally:
        shutil.rmtree(tmp)
test("写入 movie.nfo 再读回", test_nfo_write_read)

def test_nfo_tvshow_write_read():
    """写入 tvshow.nfo 再读回来"""
    from nfo_handler import write_tvshow_nfo, read_nfo
    from tmdb_client import ScrapeResult
    tmp = tempfile.mkdtemp()
    try:
        scrape = ScrapeResult(
            tmdb_id=87108, media_type="tv", title="切尔诺贝利",
            original_title="Chernobyl", english_title="Chernobyl",
            year="2019", rating=9.4, genres=["剧情", "历史"],
            status="Ended",
        )
        write_tvshow_nfo(tmp, scrape)
        assert os.path.exists(os.path.join(tmp, "tvshow.nfo"))
        data = read_nfo(tmp)
        assert data["title"] == "切尔诺贝利"
        assert data["media_type"] == "tvshow"
    finally:
        shutil.rmtree(tmp)
test("写入 tvshow.nfo 再读回", test_nfo_tvshow_write_read)

def test_nfo_episode_write_read():
    """写入 episode.nfo 再读回来"""
    from nfo_handler import write_episode_nfo, read_video_nfo
    from tmdb_client import ScrapeResult
    tmp = tempfile.mkdtemp()
    try:
        video_path = os.path.join(tmp, "S01E01.mkv")
        with open(video_path, "w") as f:
            f.write("fake")
        scrape = ScrapeResult(
            tmdb_id=87108, media_type="episode", title="1:23:45",
            episode_title="1:23:45", season_number=1, episode_number=1,
            rating=9.0,
        )
        write_episode_nfo(video_path, scrape, showtitle="切尔诺贝利")
        nfo_path = os.path.join(tmp, "S01E01.nfo")
        assert os.path.exists(nfo_path)
        data = read_video_nfo(video_path)
        assert data is not None
        assert data["season_number"] == 1
        assert data["episode_number"] == 1
    finally:
        shutil.rmtree(tmp)
test("写入 episode.nfo 再读回", test_nfo_episode_write_read)

def test_is_category_folder():
    """分类目录判定"""
    from nfo_handler import _is_category_folder
    assert _is_category_folder("电影", ["a.mkv", "b.mkv", "c.mkv"]) == True
    assert _is_category_folder("动画", ["a.mkv", "b.mkv", "c.mkv"]) == True
    assert _is_category_folder("切尔诺贝利", ["E01.mkv", "E02.mkv", "E03.mkv"]) == False
    assert _is_category_folder("test", ["single.mkv"]) == False
test("分类目录判定", test_is_category_folder)

# ══════════════════════════════════════════
# 2. poster_downloader — 海报下载
# ══════════════════════════════════════════
print("\n── poster_downloader ──")

def test_poster_downloader_import():
    from poster_downloader import download_poster
test("导入 download_poster", test_poster_downloader_import)

def test_poster_download_empty_url():
    from poster_downloader import download_poster
    assert download_poster("/tmp", "") == False
    assert download_poster("/tmp", None) == False
test("空 URL 返回 False", test_poster_download_empty_url)

# ══════════════════════════════════════════
# 3. scraper re-export 兼容性
# ══════════════════════════════════════════
print("\n── scraper re-export ──")

def test_scraper_reexport():
    from scraper import (
        read_nfo, read_video_nfo, write_movie_nfo, write_tvshow_nfo,
        write_season_nfo, write_episode_nfo, download_poster,
        _is_category_folder, scrape_folder, scrape_video, batch_scrape,
    )
test("scraper re-export 全部可用", test_scraper_reexport)

# ══════════════════════════════════════════
# 4. renamer — 重命名 + 影子名
# ══════════════════════════════════════════
print("\n── renamer ──")

def test_renamer_import():
    from renamer import (
        generate_standard_name, _is_mostly_latin, _extract_english_from_filename,
        rename_videos_in_folder, generate_shadow_name_from_nfo,
        generate_folder_shadow_name, NAMING_RULES,
    )
test("导入所有函数", test_renamer_import)

def test_generate_standard_name_movie():
    """电影标准命名：中文名 + 英文名 + 年份"""
    from renamer import generate_standard_name
    name = generate_standard_name(
        "Fight.Club.1999.1080p.BluRay.mkv",
        {"title": "搏击俱乐部", "english_title": "Fight Club", "year": "1999"},
    )
    assert "搏击俱乐部" in name
    assert "Fight Club" in name
    assert "(1999)" in name
    assert name.endswith(".mkv")
test("电影标准命名", test_generate_standard_name_movie)

def test_generate_standard_name_episode():
    """剧集标准命名：剧名 + SxxExx"""
    from renamer import generate_standard_name
    name = generate_standard_name(
        "Chernobyl.S01E03.1080p.mkv",
        {"title": "切尔诺贝利", "english_title": "Chernobyl", "year": "2019"},
        folder_title="切尔诺贝利",
    )
    assert "切尔诺贝利" in name
    assert "S01E03" in name
    assert name.endswith(".mkv")
test("剧集标准命名", test_generate_standard_name_episode)

def test_generate_standard_name_collection():
    """电影聚合命名：不按剧集格式"""
    from renamer import generate_standard_name
    name = generate_standard_name(
        "壳中少女 压缩.2010.mkv",
        {"title": "壳中少女 压缩", "year": "2010"},
        is_collection=True,
    )
    assert "壳中少女" in name
    assert "(2010)" in name
    assert "S0" not in name  # 不应有集号
test("电影聚合命名", test_generate_standard_name_collection)

def test_generate_standard_name_no_scrape():
    """无刮削数据时从文件名清洗"""
    from renamer import generate_standard_name
    name = generate_standard_name(
        "[电影天堂www.dy2018.com]星球大战前传1幽灵的威胁BD双语双字修复版.mkv"
    )
    assert "电影天堂" not in name  # 广告站名应被清除
    assert "www" not in name
    assert name.endswith(".mkv")
test("无刮削数据清洗命名", test_generate_standard_name_no_scrape)

def test_is_mostly_latin():
    from renamer import _is_mostly_latin
    assert _is_mostly_latin("Fight Club") == True
    assert _is_mostly_latin("搏击俱乐部") == False
    assert _is_mostly_latin("Fate/stay night") == True
    assert _is_mostly_latin("") == False
    assert _is_mostly_latin("ABC你好") == True  # 拉丁字母占多数
test("拉丁字母判定", test_is_mostly_latin)

def test_extract_english():
    from renamer import _extract_english_from_filename
    assert _extract_english_from_filename("搏击俱乐部 Fight Club (1999)") == "Fight Club"
    assert _extract_english_from_filename("纯中文名") == ""
    assert _extract_english_from_filename("") == ""
    # 过滤纯质量标签
    assert _extract_english_from_filename("BluRay") == ""
test("英文名提取", test_extract_english)

def test_shadow_name_from_nfo():
    """从 NFO 生成影子名"""
    from nfo_handler import write_movie_nfo, write_episode_nfo
    from renamer import generate_shadow_name_from_nfo
    from tmdb_client import ScrapeResult
    tmp = tempfile.mkdtemp()
    try:
        # 电影
        scrape = ScrapeResult(
            tmdb_id=550, media_type="movie", title="搏击俱乐部",
            original_title="Fight Club", year="1999",
        )
        write_movie_nfo(tmp, scrape)
        video = os.path.join(tmp, "test.mkv")
        with open(video, "w") as f: f.write("fake")
        shadow = generate_shadow_name_from_nfo(video, tmp, "movie")
        assert shadow is not None
        assert "搏击俱乐部" in shadow
        assert "Fight Club" in shadow
        assert "(1999)" in shadow
    finally:
        shutil.rmtree(tmp)
test("电影影子名生成", test_shadow_name_from_nfo)

# ══════════════════════════════════════════
# 5. organizer re-export 兼容性
# ══════════════════════════════════════════
print("\n── organizer re-export ──")

def test_organizer_reexport():
    from organizer import (
        # 分类核心（原生）
        classify_folder, _is_ignorable_subdir, _is_season_dir,
        _extract_season_number, _get_season_number, _count_episode_files,
        _is_series_collection, infer_category_tag, get_category_tag,
        scrape_supplement, _has_poster,
        # re-export from renamer
        generate_standard_name, _is_mostly_latin, rename_videos_in_folder,
        generate_shadow_name_from_nfo, generate_folder_shadow_name, NAMING_RULES,
        # re-export from structure_organizer
        reorganize_seasons, reorganize_seasons_by_nfo,
        wrap_loose_videos_in_category, organize_folder,
        merge_scattered_seasons, smart_archive_plan,
        smart_archive_recursive, execute_archive_plan,
    )
test("organizer re-export 全部可用", test_organizer_reexport)

def test_classify_folder_movie():
    """电影文件夹分类"""
    from organizer import classify_folder
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp, "movie.mkv"), "w") as f: f.write("fake")
        result = classify_folder(tmp)
        assert result["type"] == "movie"
    finally:
        shutil.rmtree(tmp)
test("电影文件夹分类", test_classify_folder_movie)

def test_classify_folder_tv():
    """TV 文件夹分类（有季目录）"""
    from organizer import classify_folder
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "Season 01"))
        os.makedirs(os.path.join(tmp, "Season 02"))
        result = classify_folder(tmp)
        assert result["type"] == "tv"
    finally:
        shutil.rmtree(tmp)
test("TV 文件夹分类", test_classify_folder_tv)

def test_is_season_dir():
    from organizer import _is_season_dir
    assert _is_season_dir("Season 01") == True
    assert _is_season_dir("S03") == True
    assert _is_season_dir("第5季") == True
    assert _is_season_dir("OVA") == True
    assert _is_season_dir("特别篇") == True
    assert _is_season_dir("剧场版") == True
    assert _is_season_dir("电影") == False
    assert _is_season_dir("字幕") == False
test("季目录判定", test_is_season_dir)

def test_extract_season_number():
    from organizer import _extract_season_number
    assert _extract_season_number("Season 01") == 1
    assert _extract_season_number("S03") == 3
    assert _extract_season_number("第5季") == 5
    assert _extract_season_number("第一季") == 1
    assert _extract_season_number("OVA") is None
test("季号提取", test_extract_season_number)

def test_is_ignorable_subdir():
    from organizer import _is_ignorable_subdir
    assert _is_ignorable_subdir("subs") == True
    assert _is_ignorable_subdir("Subtitles") == True
    assert _is_ignorable_subdir("extras") == True
    assert _is_ignorable_subdir("@eaDir") == True
    assert _is_ignorable_subdir("Season 01") == False
    assert _is_ignorable_subdir("切尔诺贝利") == False
test("可忽略子目录判定", test_is_ignorable_subdir)

def test_infer_category_tag():
    from organizer import infer_category_tag
    assert infer_category_tag("电影") == "movie"
    assert infer_category_tag("电视剧") == "tv"
    assert infer_category_tag("动画番") == "tv"
    assert infer_category_tag("综艺") == "tv"
    assert infer_category_tag("纪录片") == "tv"
    assert infer_category_tag("动画电影") == "movie"
    assert infer_category_tag("未知分类") == "movie"  # 默认 movie
test("一级分类标签推断", test_infer_category_tag)

# ══════════════════════════════════════════
# 6. structure_organizer — 结构整理
# ══════════════════════════════════════════
print("\n── structure_organizer ──")

def test_structure_organizer_import():
    from structure_organizer import (
        reorganize_seasons, reorganize_seasons_by_nfo,
        wrap_loose_videos_in_category, organize_folder,
        merge_scattered_seasons, smart_archive_plan,
        smart_archive_recursive, execute_archive_plan,
    )
test("导入所有函数", test_structure_organizer_import)

def test_smart_archive_plan_empty():
    """空目录返回空 plan"""
    from structure_organizer import smart_archive_plan
    tmp = tempfile.mkdtemp()
    try:
        plan = smart_archive_plan(tmp)
        assert plan == []
    finally:
        shutil.rmtree(tmp)
test("空目录归档 plan 为空", test_smart_archive_plan_empty)

def test_smart_archive_plan_with_orphan():
    """有孤立海报但无有效 NFO → 应产生清理 plan"""
    from structure_organizer import smart_archive_plan
    tmp = tempfile.mkdtemp()
    try:
        # 创建一个无效的 NFO（空文件）和一个海报
        with open(os.path.join(tmp, "movie.nfo"), "w") as f: f.write("")
        with open(os.path.join(tmp, "poster.jpg"), "wb") as f: f.write(b"\xff\xd8")
        plan = smart_archive_plan(tmp)
        # 无效 NFO + 海报应该被标记清理
        assert len(plan) >= 1
        assert plan[0]["action"] == "archive_and_delete"
    finally:
        shutil.rmtree(tmp)
test("孤立海报产生清理 plan", test_smart_archive_plan_with_orphan)

def test_smart_archive_plan_valid_nfo():
    """有效 NFO 的目录不产生清理 plan"""
    from structure_organizer import smart_archive_plan
    from nfo_handler import write_movie_nfo
    from tmdb_client import ScrapeResult
    tmp = tempfile.mkdtemp()
    try:
        scrape = ScrapeResult(tmdb_id=1, media_type="movie", title="测试电影", year="2024")
        write_movie_nfo(tmp, scrape)
        with open(os.path.join(tmp, "poster.jpg"), "wb") as f: f.write(b"\xff\xd8")
        plan = smart_archive_plan(tmp)
        assert plan == []  # 有效 NFO，不清理
    finally:
        shutil.rmtree(tmp)
test("有效 NFO 不清理", test_smart_archive_plan_valid_nfo)

def test_reorganize_seasons_dry_run():
    """扁平 TV 目录 dry_run → 生成移动操作"""
    from structure_organizer import reorganize_seasons
    tmp = tempfile.mkdtemp()
    try:
        # 创建扁平 TV 目录（无季子目录，有视频）
        for i in range(1, 4):
            with open(os.path.join(tmp, f"E{i:02d}.mkv"), "w") as f: f.write("fake")
        result = reorganize_seasons(tmp, dry_run=True, category_hint="tv")
        assert result["status"] == "ok"
        assert result["count"] > 0  # 应该有移动操作
        # 验证操作是移到 Season 01
        for op in result["ops"]:
            if op["action"] == "move":
                assert "Season 01" in op["new"]
    finally:
        shutil.rmtree(tmp)
test("扁平 TV 季化 dry_run", test_reorganize_seasons_dry_run)

# ══════════════════════════════════════════
# 7. 路由模块导入
# ══════════════════════════════════════════
print("\n── 路由模块 ──")

def test_routes_import():
    from routes.media_info import router as r1
    from routes.poster import router as r2
    from routes.relocate import router as r3
    from routes.analyze import router as r4
    from routes.scrape import router as r5
    from routes.organize import router as r6
    assert r1 is not None
    assert r2 is not None
    assert r3 is not None
    assert r4 is not None
    assert r5 is not None
    assert r6 is not None
test("6 个路由模块全部可导入", test_routes_import)

def test_main_app_routes():
    """验证 main.py 注册了所有关键路由"""
    from main import app
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    critical = [
        "/scrape/candidates", "/scrape/douban", "/scrape/bangumi",
        "/scrape/poster", "/proxy/image", "/scrape/upload-poster",
        "/scrape/delete-poster", "/scrape/poster-url",
        "/media/info", "/media/shadow-name",
        "/analyze/folder", "/analyze/library", "/organize/classify",
        "/organize/dry-run", "/organize/execute", "/organize/archive-both",
        "/organize/purge-old",
        "/organize/rename", "/organize/full", "/organize/rollback",
        "/scrape", "/scrape/select", "/scrape/read",
    ]
    missing = [c for c in critical if c not in paths]
    assert not missing, f"缺失路由: {missing}"
test("23 个关键路由全部注册", test_main_app_routes)

# ══════════════════════════════════════════
# 8. 跨模块集成测试
# ══════════════════════════════════════════
print("\n── 跨模块集成 ──")

def test_full_pipeline_nfo_rename_shadow():
    """完整流水线：写 NFO → 生成标准名 → 生成影子名"""
    from nfo_handler import write_movie_nfo, read_nfo
    from renamer import generate_standard_name, generate_shadow_name_from_nfo
    from tmdb_client import ScrapeResult
    tmp = tempfile.mkdtemp()
    try:
        # 1. 写 NFO
        scrape = ScrapeResult(
            tmdb_id=27205, media_type="movie", title="盗梦空间",
            original_title="Inception", english_title="Inception",
            year="2010", rating=8.8, genres=["科幻", "动作"],
        )
        write_movie_nfo(tmp, scrape)
        # 2. 读 NFO
        nfo = read_nfo(tmp)
        assert nfo["title"] == "盗梦空间"
        # 3. 生成标准名
        std_name = generate_standard_name(
            "Inception.2010.2160p.UHD.BluRay.mkv", nfo
        )
        assert "盗梦空间" in std_name
        assert "Inception" in std_name
        assert std_name.endswith(".mkv")
        # 4. 生成影子名
        video = os.path.join(tmp, "test.mkv")
        with open(video, "w") as f: f.write("fake")
        shadow = generate_shadow_name_from_nfo(video, tmp, "movie")
        assert "盗梦空间" in shadow
        assert "Inception" in shadow
        assert "(2010)" in shadow
    finally:
        shutil.rmtree(tmp)
test("完整流水线：NFO → 标准名 → 影子名", test_full_pipeline_nfo_rename_shadow)

def test_full_pipeline_tv_episode():
    """TV 流水线：写 tvshow.nfo + episode.nfo → 读回验证"""
    from nfo_handler import write_tvshow_nfo, write_episode_nfo, read_nfo, read_video_nfo
    from renamer import generate_shadow_name_from_nfo
    from tmdb_client import ScrapeResult
    tmp = tempfile.mkdtemp()
    try:
        # 写 tvshow.nfo
        tv = ScrapeResult(
            tmdb_id=87108, media_type="tv", title="切尔诺贝利",
            original_title="Chernobyl", english_title="Chernobyl",
            year="2019", rating=9.4,
        )
        write_tvshow_nfo(tmp, tv)
        # 写 episode.nfo
        video = os.path.join(tmp, "S01E01.mkv")
        with open(video, "w") as f: f.write("fake")
        ep = ScrapeResult(
            tmdb_id=87108, media_type="episode", title="1:23:45",
            episode_title="1:23:45", season_number=1, episode_number=1,
        )
        write_episode_nfo(video, ep, showtitle="切尔诺贝利")
        # 读回验证
        tv_nfo = read_nfo(tmp)
        assert tv_nfo["title"] == "切尔诺贝利"
        ep_nfo = read_video_nfo(video)
        assert ep_nfo["season_number"] == 1
        assert ep_nfo["episode_number"] == 1
        # 影子名
        shadow = generate_shadow_name_from_nfo(video, tmp, "tv")
        assert shadow is not None
        assert "切尔诺贝利" in shadow
        assert "S01E01" in shadow
    finally:
        shutil.rmtree(tmp)
test("TV 流水线：tvshow + episode NFO → 影子名", test_full_pipeline_tv_episode)

def test_classify_then_reorganize():
    """分类 → 季化：先判断类型再整理"""
    from organizer import classify_folder
    from structure_organizer import reorganize_seasons
    tmp = tempfile.mkdtemp()
    try:
        for i in range(1, 6):
            with open(os.path.join(tmp, f"E{i:02d}.mkv"), "w") as f: f.write("fake")
        # 分类
        info = classify_folder(tmp, category_hint="tv")
        assert info["type"] == "tv"
        # 季化 dry_run
        result = reorganize_seasons(tmp, dry_run=True, category_hint="tv")
        assert result["count"] == 5  # 5 个视频移到 Season 01
    finally:
        shutil.rmtree(tmp)
test("分类 → 季化集成", test_classify_then_reorganize)

# ══════════════════════════════════════════
# 总结
# ══════════════════════════════════════════
print("\n" + "=" * 60)
total = passed + failed
if failed == 0:
    print(f"全部通过 ✓ ({passed}/{total})")
else:
    print(f"有失败 ✗ ({passed} 通过, {failed} 失败, 共 {total})")
print("=" * 60)
