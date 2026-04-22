import os
import logging
import shutil

logger = logging.getLogger(__name__)
SANDBOX_DIR = os.path.join(os.path.dirname(__file__), "test_sandbox")

def create_file(path, content="", size=0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        # 空文件或者轻度文本，完全0字节体积也可以
        f.write(content)
        if size > 0:
            f.truncate(size)

def reset_sandbox():
    if os.path.exists(SANDBOX_DIR):
        shutil.rmtree(SANDBOX_DIR)
    os.makedirs(SANDBOX_DIR)

    # ---------------- 场景 1：基础的洗版测试 ---------------- 
    matrix_dir = os.path.join(SANDBOX_DIR, "视频", "电影", "The Matrix (1999)")
    create_file(os.path.join(matrix_dir, "The Matrix (1999) - 1080p.old.mkv"), "")
    create_file(os.path.join(matrix_dir, "The.Matrix.1999.2160p.WEB-DL.mkv"), "")
    create_file(os.path.join(matrix_dir, "The Matrix (1999).nfo"), "<movie><title>The Matrix</title></movie>")

    # ---------------- 场景 2：比较规矩但是夹带散兵的剧集 ---------------- 
    bb_dir = os.path.join(SANDBOX_DIR, "视频", "剧集", "Breaking Bad")
    create_file(os.path.join(bb_dir, "tvshow.nfo"), "<tvshow><title>Breaking Bad</title></tvshow>")
    
    s1_dir = os.path.join(bb_dir, "Season 01")
    create_file(os.path.join(s1_dir, "Breaking Bad S01E01 1080p.mkv"), "")
    create_file(os.path.join(s1_dir, "Breaking.Bad.S01E01.2160p.UHD.mkv"), "") # 要替换旧文件
    create_file(os.path.join(s1_dir, "Breaking Bad S01E01 1080p.nfo"), "<title>Pilot</title>")

    create_file(os.path.join(bb_dir, "Breaking.Bad.S01E02.1080p.mkv"), "") # 游荡的一集

    # ---------------- 场景 3：[名字极其混乱] 的裸奔动漫 ---------------- 
    anime_dir = os.path.join(SANDBOX_DIR, "视频", "动画番", "Eighty Six")
    # 没有 S 标识，只有乱七八糟的字幕组前缀和直接跟集数
    create_file(os.path.join(anime_dir, "[Nyuu] 86 - EIGHTY SIX - 02 (1080p).mkv"), "")
    create_file(os.path.join(anime_dir, "[Nyuu] 86 - EIGHTY SIX - 03 (1080p).mkv"), "")

    # ---------------- 场景 4：[结构错位 + 极度大杂烩] 灾难现场 ---------------- 
    disaster_dir = os.path.join(SANDBOX_DIR, "视频", "下载区", "[XXX广告组首发] 混杂乱炖不知名影视大包")
    # 里面是一层套一层的混乱
    create_file(os.path.join(disaster_dir, "video1_unknown.mp4"), "")
    create_file(os.path.join(disaster_dir, "subtitles", "cn", "video1.ass"), "")
    create_file(os.path.join(disaster_dir, "random_movie_inside.mkv"), "")

    # ---------------- 场景 5：[标准化彻底缺失] 根本没有剧集文件夹的多季糊涂账 ---------------- 
    messy_tv_dir = os.path.join(SANDBOX_DIR, "视频", "剧集", "The Boys")
    # 第1季、第2季全都裸装在根目录下，毫不区分
    create_file(os.path.join(messy_tv_dir, "The Boys S01E01 1080p.mkv"), "")
    create_file(os.path.join(messy_tv_dir, "The Boys S02E01 1080p.mkv"), "")
    create_file(os.path.join(messy_tv_dir, "The Boys Season 1 Episode 2.mkv"), "") # 完全不规范的书写

    # ---------------- 场景 6：刚下好的全损命名夹 ---------------- 
    new_dl_dir = os.path.join(SANDBOX_DIR, "视频", "下载区", " Breaking.Bad.S01E03.1080p.WEB-DL")
    create_file(os.path.join(new_dl_dir, "bb.s01e03.mkv"), "")
    
    # ---------------- 场景 7：[重度嵌套/附带资料的高玩库] 黑礁 / 妖精的旋律 ---------------- 
    black_lagoon_dir = os.path.join(SANDBOX_DIR, "视频", "动画番", "Black Lagoon")
    
    # 1. 散乱的正片（没有季号，各种压制组前缀）
    create_file(os.path.join(black_lagoon_dir, "[VCB-S] Black Lagoon [01] [1080p].mkv"), "")
    create_file(os.path.join(black_lagoon_dir, "[VCB-S] Black Lagoon [02] [1080p].mkv"), "")
    
    # 2. 内含极度深层嵌套的第二季（被无意包裹）
    create_file(os.path.join(black_lagoon_dir, "Black Lagoon The Second Barrage", "Video", "[VCB-S] Black Lagoon The Second Barrage [13] [1080p].mkv"), "")
    
    # 3. 音乐与设定集（必须被屏蔽）
    create_file(os.path.join(black_lagoon_dir, "OST (Original Soundtrack)", "track01.mp3"), "")
    create_file(os.path.join(black_lagoon_dir, "Scans", "artbook_01.jpg"), "") 
    
    # 4. 深层嵌套的 OVA（用户担心的点）: 被藏在各种莫名其妙的层级里
    create_file(os.path.join(black_lagoon_dir, "Extras", "Roberta's Blood Trail", "Black Lagoon OVA 01.mkv"), "")
    create_file(os.path.join(black_lagoon_dir, "Extras", "Roberta's Blood Trail", "Black Lagoon OVA 02.mkv"), "")
    
    # 外层还有妖精的旋律乱放的剧集
    elfen_dir = os.path.join(SANDBOX_DIR, "视频", "动画番", "Elfen Lied", "Elfen Lied Episodes", "Subbed")
    create_file(os.path.join(elfen_dir, "Elfen Lied 01 (1080p).mkv"), "")
    create_file(os.path.join(elfen_dir, "Elfen Lied SP.mkv"), "") # 特典文件
    
    logger.info(f"✅ '地狱级难度的沙盘' 已重置: {SANDBOX_DIR}")

if __name__ == "__main__":
    reset_sandbox()
