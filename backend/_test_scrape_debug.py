import requests
# 模拟刮削西部世界第2季
import os
base = "\\\\DS218play\\share\\视频\\电视剧"
for d in os.listdir(base):
    if "西部世界" in d:
        dp = os.path.join(base, d)
        subs = [s for s in os.listdir(dp) if os.path.isdir(os.path.join(dp, s))]
        print(f"{d}: {subs}")
        for s in subs:
            if "2" in s or "S02" in s or "02" in s:
                sp = os.path.join(dp, s)
                print(f"  测试路径: {sp}")
                # 读 NFO
                import sys; sys.path.insert(0, ".")
                import scraper
                nfo = scraper.read_nfo(sp)
                print(f"  NFO: title={nfo.get('title') if nfo else 'None'}")
