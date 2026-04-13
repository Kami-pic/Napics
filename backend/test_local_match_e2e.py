"""端到端测试：用真实媒体库 + 真实推荐数据测试本地匹配率"""
import json
import os
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from local_media_matcher import LocalMediaMatcher

# 1. 加载真实媒体库，构建索引
lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.json")
with open(lib_path, "r", encoding="utf-8") as f:
    lib = json.load(f)

matcher = LocalMediaMatcher()
matcher.build_index(lib)

# 2. 从媒体库中提取所有唯一的 clean_name（按文件夹聚合）
folders = {}
for v in lib:
    fn = v.get("folder_name", "")
    if fn not in folders:
        folders[fn] = {
            "clean_names": set(),
            "shadow_names": set(),
            "tmdb_ids": set(),
            "max_height": 0,
        }
    cn = v.get("clean_name", "").strip()
    if cn:
        folders[fn]["clean_names"].add(cn)
    sn = v.get("shadow_name", "").strip()
    if sn:
        folders[fn]["shadow_names"].add(sn)
    tid = v.get("shadow_tmdb_id")
    if tid:
        folders[fn]["tmdb_ids"].add(tid)
    h = v.get("height") or 0
    if h > folders[fn]["max_height"]:
        folders[fn]["max_height"] = h

# 3. 用媒体库自身的数据模拟推荐条目，测试自匹配率
print(f"\n=== 自匹配测试（媒体库 → 匹配自己）===")
print(f"总文件夹: {len(folders)}")

matched = 0
unmatched = []
for fn, info in folders.items():
    # 取第一个 clean_name 作为搜索词
    names = list(info["clean_names"])
    if not names:
        continue
    name = names[0]

    # 从文件夹名提取年份
    import re
    year_match = re.search(r"\b(19|20)\d{2}\b", fn)
    year = year_match.group(0) if year_match else ""

    # 模拟推荐条目
    fake_item = {
        "title": name,
        "year": year,
        "douban_id": "",
        "tmdb_id": list(info["tmdb_ids"])[0] if info["tmdb_ids"] else None,
    }
    status = matcher.match(fake_item)
    if status != "none":
        matched += 1
    else:
        unmatched.append({"folder": fn, "clean_name": name, "year": year, "height": info["max_height"]})

total = len([fn for fn, info in folders.items() if info["clean_names"]])
print(f"匹配成功: {matched}/{total} ({matched/total*100:.1f}%)")
print(f"未匹配: {len(unmatched)}")

if unmatched:
    print(f"\n--- 未匹配样本（前 20 个）---")
    for item in unmatched[:20]:
        print(f"  folder={item['folder'][:60]}")
        print(f"    clean_name={item['clean_name'][:50]}  year={item['year']}  height={item['height']}")

# 4. 模拟豆瓣推荐数据（用中文片名搜索）
print(f"\n=== 模拟豆瓣推荐匹配测试 ===")
# 挑一些库里可能有的热门中文片名
test_titles = [
    ("你的名字。", "2016"),
    ("流浪地球", "2019"),
    ("千年女优", "2002"),
    ("天气之子", "2019"),
    ("铃芽之旅", "2022"),
    ("灌篮高手", "2022"),
    ("进击的巨人", ""),
    ("鬼灭之刃", ""),
    ("完全不存在的电影", "2099"),
]
for title, year in test_titles:
    item = {"title": title, "year": year, "douban_id": "", "tmdb_id": None}
    status = matcher.match(item)
    print(f"  {title} ({year}) -> {status}")
