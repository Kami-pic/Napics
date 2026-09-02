"""DetailDrawer 拆分后操作测试 — 每个操作独立，不级联"""
import requests, json, sys, os, time

# 这一组直接对运行中的后端发 HTTP 请求。后端没起时应当 skip 而不是 fail —— 
# 否则真实问题会被一堆 ConnectionError 淹掉。
from test_support.live_backend import requires_live_backend

pytestmark = requires_live_backend
BASE = "http://localhost:8000"
P = F = 0

def check(l, c, d=""):
    global P, F
    if c: P+=1; print(f"  ✅ {l}")
    else: F+=1; print(f"  ❌ {l} {d}")

def post(url, params=None, jb=None, t=20):
    try:
        r = requests.post(f"{BASE}{url}", params=params, json=jb, timeout=t)
        return r.json()
    except Exception as e: return {"_error": str(e)}

def get(url, params=None, t=15):
    try: return requests.get(f"{BASE}{url}", params=params, timeout=t).json()
    except Exception as e: return {"_error": str(e)}

MOVIE = r"\\NAS\share\视频\电影\测试文件夹\爱乐之城 La La Land (2016)"
VIDEO = MOVIE + r"\爱乐之城 La La Land (2016) 720p.mp4"
ANIME = r"\\NAS\share\视频\动画番\测试动画合集\自由的她们"
ANIME_VID = ANIME + r"\自由的她们.Libres.EP1.720p.WEBrip.中法双语.弯弯字幕组.mp4"
COLLECTION = r"\\NAS\share\视频\电影\测试文件夹"
MOVE_TGT = r"\\NAS\share\视频\其他视频\洗版测试"

if __name__ == "__main__":
    print("🧪 DetailDrawer 操作测试\n")
    requests.get(f"{BASE}/config", timeout=5)
    check("后端在线", True)

    # 1. 切换文件夹类型
    print(f"\n{'='*50}\n1. 切换文件夹类型")
    d = post("/library/folder-type", jb={"path": MOVIE, "folder_type": "tv"})
    check("切换 movie→tv", d.get("status") == "ok" or "_error" not in d, json.dumps(d, ensure_ascii=False)[:80])
    d = post("/library/folder-type", jb={"path": MOVIE, "folder_type": "movie"})
    check("切回 tv→movie", d.get("status") == "ok" or "_error" not in d)

    # 2. 影子名
    print(f"\n{'='*50}\n2. 影子名")
    d = post("/media/shadow-name", jb={"file_path": VIDEO, "shadow_name": "La La Land (2016)", "source": "manual"})
    check("设置影子名", "_error" not in d, d.get("_error",""))
    d = post("/media/shadow-name", jb={"file_path": VIDEO, "shadow_name": "", "source": "manual"})
    check("清空影子名", "_error" not in d)

    # 3. 清洗名
    print(f"\n{'='*50}\n3. 清洗名")
    d = post("/library/clean-name", jb={"file_path": VIDEO, "clean_name": "La La Land"})
    check("设置清洗名", "_error" not in d, d.get("_error",""))
    d = post("/library/clean-name", jb={"file_path": VIDEO, "clean_name": ""})
    check("清空清洗名", "_error" not in d)

    # 4. 换封面（用 TMDB 图片，需要代理）
    print(f"\n{'='*50}\n4. 换封面")
    d = post("/scrape/poster-url", params={"path": MOVIE, "url": "https://image.tmdb.org/t/p/w200/qJ2tW6WMUDux911BTUgMe1nNaD3.jpg"})
    check(f"设置封面 API: {d.get('status','?')}", d.get("status") == "ok", json.dumps(d, ensure_ascii=False)[:80])
    # 验证
    time.sleep(2)
    try:
        r = requests.get(f"{BASE}/scrape/poster", params={"path": MOVIE}, timeout=10)
        check(f"读取封面 HTTP {r.status_code}", r.status_code == 200)
    except Exception as e:
        check("读取封面", False, str(e))

    # 5. 删除封面
    print(f"\n{'='*50}\n5. 删除封面")
    d = post("/scrape/delete-poster", params={"path": MOVIE})
    check("删除封面", "_error" not in d, d.get("_error",""))

    # 6. 刮削 + 读取 + 删除刮削
    print(f"\n{'='*50}\n6. 刮削 + 读取 + 删除刮削")
    d = get("/scrape", params={"name": "爱乐之城 La La Land", "path": MOVIE}, t=25)
    check("一键刮削", "_error" not in d, d.get("_error",""))
    d = get("/scrape/read", params={"path": MOVIE})
    title = (d.get("data") or {}).get("title", "")
    check(f"读取刮削: title={title}", d.get("status") == "ok" and bool(title))
    d = post("/scrape/delete-scrape", params={"path": MOVIE})
    check("删除刮削", "_error" not in d)
    d = get("/scrape/read", params={"path": MOVIE})
    check(f"刮削已删除: status={d.get('status')}", d.get("status") == "not_found")
    # 恢复刮削
    d = get("/scrape", params={"name": "爱乐之城 La La Land", "path": MOVIE}, t=25)
    check("恢复刮削", "_error" not in d)

    # 7. 禁止刮削
    print(f"\n{'='*50}\n7. 禁止刮削")
    d = post("/no-scrape", params={"path": MOVIE, "block": "true"})
    check("设置禁止", "_error" not in d)
    d = get("/no-scrape")
    in_list = MOVIE in (d or [])
    check(f"在禁止列表: {in_list}", in_list)
    d = post("/no-scrape", params={"path": MOVIE, "block": "false"})
    check("解除禁止", "_error" not in d)

    # 8. 自动命名预览（动画）
    print(f"\n{'='*50}\n8. 自动命名预览")
    d = post("/organize/rename", params={"path": ANIME, "dry_run": "true"})
    items = d.get("items", [])
    changed = [i for i in items if not i.get("unchanged")]
    check(f"自动命名: {len(items)} 项, 需改 {len(changed)} 项", len(items) > 0)

    # 9. 标准结构预览（动画）
    print(f"\n{'='*50}\n9. 标准结构预览")
    d = post("/organize/structure", params={"path": ANIME, "dry_run": "true"})
    ops = d.get("ops", [])
    check(f"标准结构: {len(ops)} 操作", len(ops) > 0)

    # 10. 一键整理预览（动画）
    print(f"\n{'='*50}\n10. 一键整理预览")
    d = post("/organize/full", params={"path": ANIME, "dry_run": "true"}, t=60)
    s = d.get("summary", {})
    check(f"一键整理: type={d.get('folder_type')} vids={s.get('total_videos',0)}", s.get("total_videos", 0) > 0)

    # 11. 复制（用动画的一个视频）
    print(f"\n{'='*50}\n11. 复制")
    d = post("/batch_manage", jb={"action": "copy", "paths": [ANIME_VID], "target_dir": MOVE_TGT})
    check("复制接口", "_error" not in d, d.get("_error",""))
    copied = os.path.join(MOVE_TGT, os.path.basename(ANIME_VID))
    time.sleep(2)
    check(f"副本存在: {os.path.isfile(copied)}", os.path.isfile(copied))
    # 清理
    if os.path.isfile(copied):
        os.remove(copied)

    # 12. 从媒体库移除（不删文件）
    print(f"\n{'='*50}\n12. 从媒体库移除")
    d = post("/batch_manage", jb={"action": "remove", "paths": [VIDEO]})
    check("移除接口", "_error" not in d, d.get("_error",""))
    check("文件仍在", os.path.isfile(VIDEO))

    print(f"\n{'='*50}")
    print(f"📊 结果: {P} 通过, {F} 失败")
    sys.exit(1 if F else 0)
