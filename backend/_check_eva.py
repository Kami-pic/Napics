import os
p = r"\\DS218play\share\视频\动画电影\福音战士新剧场版 Evangelion 三部曲"
for d in sorted(os.listdir(p)):
    dp = os.path.join(p, d)
    if os.path.isdir(dp):
        nfos = [f for f in os.listdir(dp) if f.endswith('.nfo')]
        zips = [f for f in os.listdir(dp) if f.endswith('.zip')]
        print(f"📁 {d[:40]}")
        if nfos: print(f"  NFO: {nfos}")
        if zips: print(f"  ZIP: {zips}")
    elif d.endswith('.nfo'):
        print(f"📄 {d}")
