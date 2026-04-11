"""测试封装文件夹移动/复制修复"""
import os, requests, json, time, shutil, sys
BASE = "http://localhost:8000"
P = F = 0

def check(l, c, d=""):
    global P, F
    if c: P+=1; print(f"  ✅ {l}")
    else: F+=1; print(f"  ❌ {l} {d}")

# 测试路径
MOVIE_FOLDER = r"\\DS218play\share\视频\电影\测试文件夹\爱乐之城 La La Land (2016)"
MOVIE_VIDEO = MOVIE_FOLDER + r"\爱乐之城 La La Land (2016) 720p.mp4"
TARGET = r"\\DS218play\share\视频\其他视频\洗版测试"
ANIME_FOLDER = r"\\DS218play\share\视频\动画番\测试动画合集\自由的她们"
ANIME_VIDEO = ANIME_FOLDER + r"\自由的她们.Libres.EP1.720p.WEBrip.中法双语.弯弯字幕组.mp4"

print("🧪 封装文件夹移动/复制测试\n")

# ── 测试 1：封装文件夹移动（爱乐之城：1视频+0子目录 → 应移动整个文件夹）──
print("=" * 50)
print("1. 封装文件夹移动（爱乐之城）")
print(f"   视频: {os.path.isfile(MOVIE_VIDEO)}")
print(f"   文件夹内容: {os.listdir(MOVIE_FOLDER)}")

r = requests.post(f"{BASE}/batch_manage", json={"action": "move", "paths": [MOVIE_VIDEO], "target_dir": TARGET}, timeout=20)
d = r.json()
print(f"   API: {json.dumps(d, ensure_ascii=False)[:150]}")
time.sleep(2)

moved_folder = os.path.join(TARGET, "爱乐之城 La La Land (2016)")
check("整个封装文件夹已移动", os.path.isdir(moved_folder))
if os.path.isdir(moved_folder):
    contents = os.listdir(moved_folder)
    check(f"包含视频: {any(f.endswith('.mp4') for f in contents)}", any(f.endswith(".mp4") for f in contents))
    check(f"包含NFO: {any(f.endswith('.nfo') for f in contents)}", any(f.endswith(".nfo") for f in contents))
    check(f"包含海报: {any('poster' in f for f in contents)}", any("poster" in f for f in contents))
    print(f"   内容: {contents}")
    # 回退
    shutil.move(moved_folder, os.path.dirname(MOVIE_FOLDER))
    check("回退成功", os.path.isdir(MOVIE_FOLDER))
else:
    check("原文件夹还在", os.path.isdir(MOVIE_FOLDER), "可能只移了视频文件")
    # 检查目标目录
    print(f"   目标目录: {os.listdir(TARGET)}")
    # 恢复
    moved_vid = os.path.join(TARGET, os.path.basename(MOVIE_VIDEO))
    if os.path.isfile(moved_vid):
        shutil.move(moved_vid, MOVIE_VIDEO)
        print("   已恢复视频文件")

# ── 测试 2：非封装文件夹移动（自由的她们：10视频 → 应只移动单个文件）──
print("\n" + "=" * 50)
print("2. 非封装文件夹移动（自由的她们 EP1）")
print(f"   视频: {os.path.isfile(ANIME_VIDEO)}")

r = requests.post(f"{BASE}/batch_manage", json={"action": "move", "paths": [ANIME_VIDEO], "target_dir": TARGET}, timeout=20)
d = r.json()
print(f"   API: {json.dumps(d, ensure_ascii=False)[:150]}")
time.sleep(2)

moved_vid = os.path.join(TARGET, os.path.basename(ANIME_VIDEO))
check("只移动了视频文件", os.path.isfile(moved_vid))
check("原文件夹仍在", os.path.isdir(ANIME_FOLDER))
# 回退
if os.path.isfile(moved_vid):
    shutil.move(moved_vid, ANIME_VIDEO)
    check("回退成功", os.path.isfile(ANIME_VIDEO))

# ── 测试 3：封装文件夹复制 ──
print("\n" + "=" * 50)
print("3. 封装文件夹复制（爱乐之城）")

r = requests.post(f"{BASE}/batch_manage", json={"action": "copy", "paths": [MOVIE_VIDEO], "target_dir": TARGET}, timeout=60)
d = r.json()
print(f"   API: {json.dumps(d, ensure_ascii=False)[:150]}")
time.sleep(2)

copied_folder = os.path.join(TARGET, "爱乐之城 La La Land (2016)")
check("整个封装文件夹已复制", os.path.isdir(copied_folder))
if os.path.isdir(copied_folder):
    contents = os.listdir(copied_folder)
    check(f"包含视频+NFO+海报", len(contents) >= 3, f"只有 {len(contents)} 个文件")
    print(f"   内容: {contents}")
check("原文件夹仍在", os.path.isdir(MOVIE_FOLDER))
# 清理
if os.path.isdir(copied_folder):
    shutil.rmtree(copied_folder)
    check("清理完成", not os.path.isdir(copied_folder))

print(f"\n{'='*50}")
print(f"📊 结果: {P} 通过, {F} 失败")
sys.exit(1 if F else 0)
