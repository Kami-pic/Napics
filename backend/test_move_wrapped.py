"""测试封装文件夹移动/复制修复"""
import os
import shutil
import time

import requests


BASE = "http://localhost:8000"

# 测试路径
MOVIE_FOLDER = r"\\DS218play\share\视频\电影\测试文件夹\爱乐之城 La La Land (2016)"
MOVIE_VIDEO = MOVIE_FOLDER + r"\爱乐之城 La La Land (2016) 720p.mp4"
TARGET = r"\\DS218play\share\视频\其他视频\洗版测试"
ANIME_FOLDER = r"\\DS218play\share\视频\动画番\测试动画合集\自由的她们"
ANIME_VIDEO = ANIME_FOLDER + r"\自由的她们.Libres.EP1.720p.WEBrip.中法双语.弯弯字幕组.mp4"


def post_batch_manage(action, paths, timeout=20):
    response = requests.post(
        f"{BASE}/batch_manage",
        json={"action": action, "paths": paths, "target_dir": TARGET},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def test_move_wrapped_movie_folder():
    assert os.path.isfile(MOVIE_VIDEO)

    post_batch_manage("move", [MOVIE_VIDEO])
    time.sleep(2)

    moved_folder = os.path.join(TARGET, "爱乐之城 La La Land (2016)")
    try:
        assert os.path.isdir(moved_folder)
        contents = os.listdir(moved_folder)
        assert any(f.endswith(".mp4") for f in contents)
        assert any(f.endswith(".nfo") for f in contents)
        assert any("poster" in f for f in contents)
    finally:
        if os.path.isdir(moved_folder):
            shutil.move(moved_folder, os.path.dirname(MOVIE_FOLDER))


def test_move_single_video_from_unwrapped_folder():
    assert os.path.isfile(ANIME_VIDEO)

    post_batch_manage("move", [ANIME_VIDEO])
    time.sleep(2)

    moved_vid = os.path.join(TARGET, os.path.basename(ANIME_VIDEO))
    try:
        assert os.path.isfile(moved_vid)
        assert os.path.isdir(ANIME_FOLDER)
    finally:
        if os.path.isfile(moved_vid):
            shutil.move(moved_vid, ANIME_VIDEO)


def test_copy_wrapped_movie_folder():
    assert os.path.isfile(MOVIE_VIDEO)

    post_batch_manage("copy", [MOVIE_VIDEO], timeout=60)
    time.sleep(2)

    copied_folder = os.path.join(TARGET, "爱乐之城 La La Land (2016)")
    try:
        assert os.path.isdir(copied_folder)
        assert len(os.listdir(copied_folder)) >= 3
        assert os.path.isdir(MOVIE_FOLDER)
    finally:
        if os.path.isdir(copied_folder):
            shutil.rmtree(copied_folder)
