import os, zipfile
p = r"\\DS218play\share\视频\电视剧\冰与火之歌1-8季"
zp = os.path.join(p, ".old_scrape.zip")
if os.path.exists(zp):
    with zipfile.ZipFile(zp, 'r') as zf:
        zf.extractall(p)
    os.remove(zp)
    print("OK parent")
for d in os.listdir(p):
    dp = os.path.join(p, d)
    if os.path.isdir(dp):
        szp = os.path.join(dp, ".old_scrape.zip")
        if os.path.exists(szp):
            with zipfile.ZipFile(szp, 'r') as zf:
                zf.extractall(dp)
            os.remove(szp)
            print(f"OK {d}")
