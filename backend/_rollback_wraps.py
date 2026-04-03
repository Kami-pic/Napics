"""回滚所有 wrap 操作：把被封装进子文件夹的视频提回父目录，删除空文件夹
回滚到"第一次删除刮削后、跑234之前"的状态
"""
import os, shutil

NAS = r"\\DS218play\share\视频"
SKIP_DIRS = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}
subtitle_exts = {'.srt','.ass','.ssa','.sub','.idx','.sup','.vtt'}

# 这些文件夹的子目录是之前整理操作创建的 wrap 文件夹
# 特征：子目录里只有1个视频（或1个视频+字幕），子目录名和视频名相似
# 需要排除的：真正的子目录结构（如季目录、系列电影子目录）

# 已知被错误 wrap 的文件夹（从 organize_snapshots 和调试结果确认）
# 以及一级分类目录下被封装的散落视频

total_moved = 0
total_rmdir = 0

def unwrap_folder(parent_path, dry_run=True):
    """检查 parent_path 下的子目录，如果是 wrap 产生的（单视频子目录），把内容提回来"""
    global total_moved, total_rmdir
    
    if not os.path.isdir(parent_path):
        return
    
    items = os.listdir(parent_path)
    subdirs = [d for d in items if os.path.isdir(os.path.join(parent_path, d)) and not d.startswith('.')]
    
    for d in subdirs:
        dp = os.path.join(parent_path, d)
        sub_items = os.listdir(dp)
        sub_files = [f for f in sub_items if os.path.isfile(os.path.join(dp, f))]
        sub_dirs = [f for f in sub_items if os.path.isdir(os.path.join(dp, f))]
        sub_videos = [f for f in sub_files if os.path.splitext(f)[1].lower() in video_exts]
        
        # 只处理"单视频子目录"（wrap 产生的特征）
        # 排除：有子目录的、有多个视频的、有 .old_scrape.zip 的（说明是原始结构）
        if len(sub_videos) != 1:
            continue
        if sub_dirs:
            continue
        if '.old_scrape.zip' in sub_items:
            continue
        
        # 额外检查：子目录名应该和视频名相似（wrap 时用清洗名命名的）
        # 或者子目录名是纯数字（如 02、03）
        
        # 把所有文件提到父目录
        for f in sub_files:
            old = os.path.join(dp, f)
            new = os.path.join(parent_path, f)
            if os.path.exists(new):
                # 同名文件已存在，跳过
                continue
            if dry_run:
                print(f"  MOVE: {d}/{f} → {os.path.basename(parent_path)}/")
            else:
                shutil.move(old, new)
            total_moved += 1
        
        # 删除空目录
        if not dry_run:
            remaining = os.listdir(dp)
            if not remaining:
                os.rmdir(dp)
                total_rmdir += 1
        else:
            total_rmdir += 1


def main():
    global total_moved, total_rmdir
    
    dry_run = "--execute" not in __import__('sys').argv
    mode = "DRY_RUN" if dry_run else "EXECUTE"
    print(f"模式: {mode}\n")
    
    # 1. 回滚一级分类目录下被封装的散落视频
    print("=== 回滚一级分类目录下的封装 ===")
    for top in sorted(os.listdir(NAS)):
        tp = os.path.join(NAS, top)
        if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
            continue
        
        before = total_moved
        unwrap_folder(tp, dry_run)
        after = total_moved
        if after > before:
            print(f"  [{top}] 回滚 {after - before} 个文件")
    
    # 2. 回滚二级文件夹里被错误 wrap 的视频
    print("\n=== 回滚二级文件夹里的错误 wrap ===")
    for top in sorted(os.listdir(NAS)):
        tp = os.path.join(NAS, top)
        if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
            continue
        for sub in sorted(os.listdir(tp)):
            sp = os.path.join(tp, sub)
            if not os.path.isdir(sp) or sub.startswith('.'):
                continue
            
            before = total_moved
            unwrap_folder(sp, dry_run)
            after = total_moved
            if after > before:
                print(f"  [{top}/{sub}] 回滚 {after - before} 个文件")
    
    print(f"\n总计: 移动 {total_moved} 个文件, 删除 {total_rmdir} 个空目录")
    if dry_run:
        print("加 --execute 执行")


if __name__ == "__main__":
    main()
