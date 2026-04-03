import os, zipfile
p = r"\\DS218play\share\视频\动画番\东京食尸鬼 Tokyo Ghoul"
for d in [p] + [os.path.join(p, x) for x in os.listdir(p) if os.path.isdir(os.path.join(p, x))]:
    zp = os.path.join(d, ".old_scrape.zip")
    if os.path.exists(zp):
        with zipfile.ZipFile(zp, 'r') as zf:
            zf.extractall(d)
        os.remove(zp)
        print(f"OK {os.path.basename(d)}")
