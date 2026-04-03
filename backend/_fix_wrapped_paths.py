"""修复被封装视频在 media_library.json 中的路径
封装操作把 动画电影/xxx.mp4 移到了 动画电影/xxx文件夹/xxx.mp4
但 library 里的 file_path 和 folder_name 还指向旧位置
"""
import os, json

NAS = r"\\DS218play\share\视频"
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

with open('media_library.json', encoding='utf-8') as f:
    lib = json.load(f)

# 建索引：filename → [actual full paths on NAS]
print("扫描 NAS...")
file_index = {}
for root, dirs, files in os.walk(NAS):
    dirs[:] = [d for d in dirs if not d.startswith('.')]
    for f in files:
        if os.path.splitext(f)[1].lower() in video_exts:
            file_index.setdefault(f, []).append(os.path.join(root, f))

fixed = 0
for v in lib:
    old_path = v.get("file_path", "")
    if os.path.exists(old_path):
        # 路径有效，但检查 folder_name 是否正确
        actual_rel = os.path.relpath(os.path.dirname(old_path), NAS)
        if v.get("folder_name", "") != actual_rel:
            v["folder_name"] = actual_rel
            fixed += 1
        continue
    
    # 路径无效，用文件名找
    fname = os.path.basename(old_path)
    candidates = file_index.get(fname, [])
    
    if len(candidates) == 1:
        new_path = candidates[0]
        v["file_path"] = new_path
        v["folder_name"] = os.path.relpath(os.path.dirname(new_path), NAS)
        fixed += 1
    elif len(candidates) > 1:
        # 多个同名，用旧路径的目录部分匹配
        old_dir = os.path.dirname(old_path).replace("\\", "/").lower()
        for c in candidates:
            c_dir = os.path.dirname(c).replace("\\", "/").lower()
            # 新路径应该包含旧路径的父目录名
            old_parts = [p for p in old_dir.split("/") if len(p) > 2]
            if any(p in c_dir for p in old_parts[-2:]):
                v["file_path"] = c
                v["folder_name"] = os.path.relpath(os.path.dirname(c), NAS)
                fixed += 1
                break

print(f"修复: {fixed} 条")

with open('media_library.json', 'w', encoding='utf-8') as f:
    json.dump(lib, f, ensure_ascii=False, indent=2)
print("已保存")
