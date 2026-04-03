"""回滚被错误 wrap 的 TV 剧集子目录
这些子目录是上一轮整理时 wrap 产生的，特征：
- 子目录名有集号（如 UN GO (10)、真探02）
- 子目录里只有1个视频 + 可能有 .old_scrape.zip
- 父目录被 classify_folder 判为 tv
"""
import sys, os, shutil
sys.path.insert(0, '.')
import organizer

NAS = r"\\DS218play\share\视频"
SKIP_DIRS = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

dry_run = "--execute" not in sys.argv
print(f"模式: {'DRY_RUN' if dry_run else 'EXECUTE'}\n")

total_moved = 0
total_rmdir = 0

for top in sorted(os.listdir(NAS)):
    tp = os.path.join(NAS, top)
    if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
        continue
    for sub in sorted(os.listdir(tp)):
        sp = os.path.join(tp, sub)
        if not os.path.isdir(sp) or sub.startswith('.'):
            continue
        
        items = os.listdir(sp)
        subdirs = [d for d in items if os.path.isdir(os.path.join(sp, d)) and not d.startswith('.')]
        loose_vids = [f for f in items if os.path.isfile(os.path.join(sp, f)) and os.path.splitext(f)[1].lower() in video_exts]
        
        if not subdirs:
            continue
        
        # 检查子目录名是否有集号规律
        ep_count = organizer._count_episode_files(subdirs)
        if ep_count < len(subdirs) * 0.5 or len(subdirs) < 3:
            continue
        
        # 检查每个子目录是否只有1个视频（wrap 特征）
        all_single = True
        for d in subdirs:
            dp = os.path.join(sp, d)
            sub_files = [f for f in os.listdir(dp) if os.path.isfile(os.path.join(dp, f))]
            sub_vids = [f for f in sub_files if os.path.splitext(f)[1].lower() in video_exts]
            if len(sub_vids) != 1:
                all_single = False
                break
        
        if not all_single:
            continue
        
        # 这是被错误 wrap 的 TV 剧集，回滚
        print(f"[{top}/{sub}] 回滚 {len(subdirs)} 个 wrap 子目录")
        for d in subdirs:
            dp = os.path.join(sp, d)
            for f in os.listdir(dp):
                fp_old = os.path.join(dp, f)
                fp_new = os.path.join(sp, f)
                if os.path.isfile(fp_old):
                    if f == '.old_scrape.zip':
                        # 删掉 wrap 子目录里的 .old_scrape.zip（这是 wrap 后产生的，不是原始的）
                        if not dry_run:
                            os.remove(fp_old)
                        continue
                    if not os.path.exists(fp_new):
                        if not dry_run:
                            shutil.move(fp_old, fp_new)
                        total_moved += 1
            if not dry_run:
                remaining = os.listdir(dp)
                if not remaining:
                    os.rmdir(dp)
                    total_rmdir += 1

print(f"\n总计: 移动 {total_moved} 个文件, 删除 {total_rmdir} 个目录")
if dry_run:
    print("加 --execute 执行")
