"""遍历 TV 标签下所有文件夹，找出缺少第1集的剧集。
区分：A类=纯丢失（所有文件都有集号但缺01），B类=有无编号文件（可能是01被改名了）
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(__file__))
from tmdb_client import parse_filename

NAS = r"\\DS218play\share\视频"
TV_CATS = {"动画番", "电视剧"}
video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}

type_a = []  # 纯丢失
type_b = []  # 有无编号文件

for cat in sorted(os.listdir(NAS)):
    if cat not in TV_CATS:
        continue
    cat_path = os.path.join(NAS, cat)
    if not os.path.isdir(cat_path):
        continue
    for show_name in sorted(os.listdir(cat_path)):
        show_path = os.path.join(cat_path, show_name)
        if not os.path.isdir(show_path) or show_name.startswith('.'):
            continue
        all_locations = {}
        direct_vids = [f for f in os.listdir(show_path)
                       if os.path.isfile(os.path.join(show_path, f))
                       and os.path.splitext(f)[1].lower() in video_exts]
        if direct_vids:
            all_locations["(root)"] = direct_vids
        for sub in sorted(os.listdir(show_path)):
            sub_path = os.path.join(show_path, sub)
            if not os.path.isdir(sub_path) or sub.startswith('.'):
                continue
            sub_vids = [f for f in os.listdir(sub_path)
                        if os.path.isfile(os.path.join(sub_path, f))
                        and os.path.splitext(f)[1].lower() in video_exts]
            if sub_vids:
                all_locations[sub] = sub_vids
        for location, vids in all_locations.items():
            if len(vids) < 2:
                continue
            with_ep = []
            without_ep = []
            for v in vids:
                parsed = parse_filename(v)
                ep = parsed.get("episode")
                if ep is not None:
                    with_ep.append((ep, v))
                else:
                    without_ep.append(v)
            if not with_ep:
                continue
            eps = sorted(set(e for e, _ in with_ep))
            if 1 in eps:
                continue
            # 跳过续季（最小集号>13说明是续季编号）
            if eps[0] > 13:
                continue
            loc_str = f"{cat}/{show_name}" if location == "(root)" else f"{cat}/{show_name}/{location}"
            ep_str = ",".join(str(e) for e in eps[:15])
            if len(eps) > 15:
                ep_str += f"...共{len(eps)}集"
            if without_ep:
                type_b.append((loc_str, ep_str, len(vids), without_ep))
            else:
                type_a.append((loc_str, ep_str, len(vids)))

print("=" * 70)
print(f"【A类】纯丢失第1集（所有文件都有集号，但缺01）：{len(type_a)} 个")
print("=" * 70)
for loc, eps, total in type_a:
    print(f"  {loc}")
    print(f"    {total}个视频, 集号: {eps}")
    print()

print("=" * 70)
print(f"【B类】缺01但有无编号文件（可能是01被改名/丢失编号）：{len(type_b)} 个")
print("=" * 70)
for loc, eps, total, no_ep_files in type_b:
    print(f"  {loc}")
    print(f"    {total}个视频, 集号: {eps}")
    print(f"    无编号文件:")
    for f in no_ep_files:
        print(f"      → {f}")
    print()
