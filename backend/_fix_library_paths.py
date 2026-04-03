"""修复 media_library.json 中因封装操作导致的路径不一致
文件已从 动画电影/xxx.mp4 移到 动画电影/xxx文件夹/xxx.mp4
但 library 里的 file_path 和 folder_name 还是旧的
"""
import sys, os, json
sys.path.insert(0, '.')

NAS = r"\\DS218play\share\视频"
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

with open('media_library.json', encoding='utf-8') as f:
    lib = json.load(f)

# 建立当前 NAS 上所有视频文件的索引：filename → full_path
print("扫描 NAS 文件...")
file_index = {}  # filename → [full_paths]
for root, dirs, files in os.walk(NAS):
    dirs[:] = [d for d in dirs if not d.startswith('.')]
    for f in files:
        if os.path.splitext(f)[1].lower() in video_exts:
            full = os.path.join(root, f)
            file_index.setdefault(f, []).append(full)

print(f"NAS 上共 {sum(len(v) for v in file_index.values())} 个视频文件")

# 修复 library 条目
fixed = 0
not_found = 0
for v in lib:
    old_path = v.get("file_path", "")
    if os.path.exists(old_path):
        continue  # 路径还有效，不用修

    # 路径无效，用文件名在索引里找
    fname = v.get("file_name", "") or os.path.basename(old_path)
    candidates = file_index.get(fname, [])

    if len(candidates) == 1:
        new_path = candidates[0]
        # 计算新的 folder_name（相对于 NAS 根目录）
        rel = os.path.relpath(os.path.dirname(new_path), NAS)
        v["file_path"] = new_path
        v["folder_name"] = rel
        fixed += 1
    elif len(candidates) > 1:
        # 多个同名文件，尝试用旧路径的部分匹配
        old_parts = old_path.replace("\\", "/").lower()
        best = None
        for c in candidates:
            c_parts = c.replace("\\", "/").lower()
            # 找包含旧路径关键部分的
            if any(p in c_parts for p in old_parts.split("/") if len(p) > 3):
                best = c
                break
        if best:
            rel = os.path.relpath(os.path.dirname(best), NAS)
            v["file_path"] = best
            v["folder_name"] = rel
            fixed += 1
        else:
            not_found += 1
            print(f"  多候选无法匹配: {fname} ({len(candidates)} candidates)")
    else:
        not_found += 1
        if "动画电影" in old_path or "电影" in old_path:
            print(f"  未找到: {fname}")

print(f"\n修复: {fixed}, 未找到: {not_found}")

# 保存
with open('media_library.json', 'w', encoding='utf-8') as f:
    json.dump(lib, f, ensure_ascii=False, indent=2)
print("已保存 media_library.json")
