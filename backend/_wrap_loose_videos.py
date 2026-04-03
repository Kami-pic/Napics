"""封装一级分类目录下的散落视频到独立文件夹
规则：每个末端视频必须有自己的文件夹
"""
import sys, os, shutil
sys.path.insert(0, '.')
from analyzer import _clean_filename_for_folder

NAS = r"\\DS218play\share\视频"
SKIP_DIRS = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}
subtitle_exts = {'.srt','.ass','.ssa','.sub','.idx','.sup','.vtt'}


def find_associated_files(folder, video_filename):
    """找到视频文件关联的字幕/NFO等文件"""
    base = os.path.splitext(video_filename)[0]
    associated = []
    for f in os.listdir(folder):
        if f == video_filename:
            continue
        fp = os.path.join(folder, f)
        if not os.path.isfile(fp):
            continue
        f_base = os.path.splitext(f)[0]
        f_ext = os.path.splitext(f)[1].lower()
        # 同名 NFO
        if f == base + ".nfo":
            associated.append(f)
        # 同名字幕
        elif f_base == base and f_ext in subtitle_exts:
            associated.append(f)
        # 同名开头的字幕（如 video.chs.srt）
        elif f.startswith(base + ".") and f_ext in subtitle_exts:
            associated.append(f)
        # 同名开头的图片（如 video-poster.jpg）
        elif f.startswith(base) and f_ext in {'.jpg', '.png'}:
            associated.append(f)
    return associated


def wrap_loose_videos(dry_run=True):
    """扫描所有一级分类目录，封装散落视频"""
    total_ops = 0

    for top in sorted(os.listdir(NAS)):
        tp = os.path.join(NAS, top)
        if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
            continue

        # 找散落视频
        loose_videos = []
        for f in os.listdir(tp):
            fp = os.path.join(tp, f)
            if os.path.isfile(fp) and os.path.splitext(f)[1].lower() in video_exts:
                loose_videos.append(f)

        if not loose_videos:
            continue

        print(f"\n[{top}] 散落视频: {len(loose_videos)}")

        for vf in loose_videos:
            # 用清洗函数生成文件夹名
            folder_name = _clean_filename_for_folder(vf)
            if not folder_name:
                folder_name = os.path.splitext(vf)[0]
            # 清理非法字符
            import re
            folder_name = re.sub(r'[<>:"/\\|?*]', '', folder_name).strip()
            if not folder_name:
                folder_name = os.path.splitext(vf)[0]

            target_dir = os.path.join(tp, folder_name)
            old_path = os.path.join(tp, vf)
            new_path = os.path.join(target_dir, vf)

            # 找关联文件
            associated = find_associated_files(tp, vf)

            if dry_run:
                print(f"  {vf}")
                print(f"    → {folder_name}/")
                if associated:
                    print(f"    + {associated}")
            else:
                os.makedirs(target_dir, exist_ok=True)
                if os.path.exists(old_path) and not os.path.exists(new_path):
                    shutil.move(old_path, new_path)
                    total_ops += 1
                    for af in associated:
                        af_old = os.path.join(tp, af)
                        af_new = os.path.join(target_dir, af)
                        if os.path.exists(af_old) and not os.path.exists(af_new):
                            shutil.move(af_old, af_new)
                            total_ops += 1
                print(f"  ✓ {vf} → {folder_name}/")

    return total_ops


if __name__ == "__main__":
    execute = "--execute" in sys.argv
    mode = "EXECUTE" if execute else "DRY_RUN"
    print(f"模式: {mode}\n")

    ops = wrap_loose_videos(dry_run=not execute)

    if execute:
        print(f"\n完成，共 {ops} 个文件移动")
    else:
        print(f"\n预览完成，加 --execute 执行")
