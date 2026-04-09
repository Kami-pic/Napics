"""验证所有前端会调用的 API 端点"""
import urllib.request
import sys

urls = [
    ("后端根路径", "http://127.0.0.1:8000/"),
    ("配置", "http://127.0.0.1:8000/config"),
    ("媒体库树", "http://127.0.0.1:8000/library/tree"),
    ("豆瓣热门", "http://127.0.0.1:8000/douban/hot?type=movie"),
    ("下载任务", "http://127.0.0.1:8000/download-manager/tasks"),
    ("下载进度", "http://127.0.0.1:8000/download-manager/progress"),
    ("搜索过滤", "http://127.0.0.1:8000/config/search-filter"),
    ("排序权重", "http://127.0.0.1:8000/config/sort-weights"),
    ("回收站", "http://127.0.0.1:8000/recycle-bin"),
    ("整理历史", "http://127.0.0.1:8000/organize/history?limit=5"),
    ("分析报告", "http://127.0.0.1:8000/analysis/report"),
    ("Alist挂载", "http://127.0.0.1:8000/alist/mounts"),
    ("种子黑名单", "http://127.0.0.1:8000/torrent-blacklist"),
    ("禁止刮削", "http://127.0.0.1:8000/no-scrape"),
    ("前端页面", "http://127.0.0.1:3031"),
]

passed = failed = 0
for name, url in urls:
    try:
        r = urllib.request.urlopen(url, timeout=15)
        if r.status == 200:
            passed += 1
            print(f"  OK  {name}")
        else:
            failed += 1
            print(f"  FAIL {name} => {r.status}")
    except Exception as e:
        failed += 1
        err = str(e)[:60]
        print(f"  FAIL {name} => {err}")

print(f"\n=== {passed}/{passed+failed} passed ===")
sys.exit(0 if failed == 0 else 1)
