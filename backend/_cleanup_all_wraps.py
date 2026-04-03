"""清理所有残留的错误 wrap 子目录（只有 .old_scrape.zip 的空目录）"""
import os

NAS = r"\\DS218play\share\视频"
SKIP_DIRS = {"其他视频"}
removed = 0

for top in sorted(os.listdir(NAS)):
    tp = os.path.join(NAS, top)
    if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
        continue
    for sub in sorted(os.listdir(tp)):
        sp = os.path.join(tp, sub)
        if not os.path.isdir(sp) or sub.startswith('.'):
            continue
        for d in list(os.listdir(sp)):
            dp = os.path.join(sp, d)
            if not os.path.isdir(dp) or d.startswith('.'):
                continue
            items = os.listdir(dp)
            if items == ['.old_scrape.zip']:
                os.remove(os.path.join(dp, '.old_scrape.zip'))
                os.rmdir(dp)
                removed += 1
                print(f"removed: {top}/{sub}/{d}")

print(f"\n清理了 {removed} 个空目录")
