import json
import os

def fix_paths():
    lib_path = 'media_library.json'
    if not os.path.exists(lib_path):
        print("❌ 错误: 找不到库文件。")
        return

    with open(lib_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    changed = 0
    # 假设根路径
    base_prefix = r"\\DS218play\share\视频"
    
    for v in data:
        fp = v.get("file_path", "")
        old_folder = v.get("folder_name", "")
        
        # 重新计算干净的相对路径
        if fp.startswith(base_prefix):
            # 获取目录部分
            real_folder_abs = os.path.dirname(fp)
            # 计算相对于 base_prefix 的相对路径
            rel = os.path.relpath(real_folder_abs, base_prefix)
            new_folder = "" if rel == "." else rel
            
            if new_folder != old_folder:
                v["folder_name"] = new_folder
                changed += 1
        
        # 强制标准化斜杠
        if "folder_name" in v:
            v["folder_name"] = v["folder_name"].replace("\\", "/")

    if changed > 0:
        with open(lib_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"✅ 修复完毕！已标准化 {changed} 条记录的路径。共 {len(data)} 条数据。")
    else:
        print("💡 路径已经很干净，无需修改。")

if __name__ == "__main__":
    fix_paths()
