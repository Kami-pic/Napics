"""清理封装电影文件夹中的重复刮削/封面文件。
只处理电影分类下的封装电影（单视频无子目录）。
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

NAS = r"\\DS218play\share\视频"
MOVIE_CATS = {"电影", "动画电影"}
video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
DRY_RUN = "--run" not in sys.argv
stats = {"scanned": 0, "cleaned": 0, "deleted": 0, "renamed": 0}

for cat in sorted(os.listdir(NAS)):
    if cat not in MOVIE_CATS:
        continue
    cat_path = os.path.join(NAS, cat)
    if not os.path.isdir(cat_path):
        continue
    for folder_name in sorted(os.listdir(cat_path)):
        folder_path = os.path.join(cat_path, folder_name)
        if not os.path.isdir(folder_path) or folder_name.startswith('.'):
            continue
        try:
            items = os.listdir(folder_path)
        except OSError:
            continue
        vids = [f for f in items if os.path.isfile(os.path.join(folder_path, f))
                and os.path.splitext(f)[1].lower() in video_exts]
        subdirs = [d for d in items if os.path.isdir(os.path.join(folder_path, d)) and not d.startswith('.')]
        if len(vids) != 1 or subdirs:
            continue
        stats["scanned"] += 1
        vid_base = os.path.splitext(vids[0])[0]
        actions = []

        # NFO: movie.nfo vs vid_base.nfo
        has_movie_nfo = "movie.nfo" in items
        named_nfo = vid_base + ".nfo"
        has_named_nfo = named_nfo in items
        if has_movie_nfo and has_named_nfo:
            g_t = os.path.getmtime(os.path.join(folder_path, "movie.nfo"))
            n_t = os.path.getmtime(os.path.join(folder_path, named_nfo))
            if n_t > g_t:
                actions.append(("replace", named_nfo, "movie.nfo"))
            else:
                actions.append(("delete", named_nfo, None))
        elif has_named_nfo and not has_movie_nfo:
            actions.append(("rename", named_nfo, "movie.nfo"))

        # Poster/fanart
        for suffix, generic in [("-poster.jpg", "poster.jpg"), ("-poster.png", "poster.jpg"),
                                 ("-fanart.jpg", "fanart.jpg"), ("-fanart.png", "fanart.jpg")]:
            named = vid_base + suffix
            if named not in items:
                continue
            has_g = generic in items
            if has_g:
                g_t = os.path.getmtime(os.path.join(folder_path, generic))
                n_t = os.path.getmtime(os.path.join(folder_path, named))
                if n_t > g_t:
                    actions.append(("replace", named, generic))
                else:
                    actions.append(("delete", named, None))
            else:
                actions.append(("rename", named, generic))

        if not actions:
            continue
        stats["cleaned"] += 1
        rel = os.path.relpath(folder_path, NAS)
        print(f"\n[{rel}]  video: {vids[0]}")
        for action, src, dst in actions:
            src_path = os.path.join(folder_path, src)
            if action == "delete":
                print(f"  DEL    {src}")
                if not DRY_RUN:
                    os.remove(src_path)
                stats["deleted"] += 1
            elif action == "rename":
                print(f"  RENAME {src} -> {dst}")
                if not DRY_RUN:
                    os.rename(src_path, os.path.join(folder_path, dst))
                stats["renamed"] += 1
            elif action == "replace":
                print(f"  REPLACE {dst} <- {src}")
                if not DRY_RUN:
                    dst_path = os.path.join(folder_path, dst)
                    if os.path.exists(dst_path):
                        os.remove(dst_path)
                    os.rename(src_path, dst_path)
                stats["renamed"] += 1

mode = "DRY RUN" if DRY_RUN else "EXECUTED"
print(f"\n{'='*60}")
print(f"[{mode}] Scanned {stats['scanned']} wrapped movies")
print(f"  Need cleanup: {stats['cleaned']}")
print(f"  Delete: {stats['deleted']}")
print(f"  Rename: {stats['renamed']}")
if DRY_RUN:
    print("\nAdd --run to execute")
