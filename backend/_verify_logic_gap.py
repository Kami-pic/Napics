import json
import os
import sys

# 注入 backend 目录
sys.path.append(os.getcwd())

from main import get_library_tree

def verify():
    lib_path = 'media_library.json'
    if not os.path.exists(lib_path):
        print("❌ 核心数据库丢失")
        return

    with open(lib_path, 'r', encoding='utf-8') as f:
        lib = json.load(f)

    # 寻找有译名的条目
    has_shadow = [v for v in lib if v.get('shadow_name')]
    if not has_shadow:
        print("💡 数据库中竟然也没有译名，说明之前的 NFO 恢复脚本没能成功注入。")
        return

    # 模拟 API 调用生成树状图
    print("[*] 正在模拟生成 UI 树状图...")
    tree = get_library_tree()

    def find_node(node, target_path):
        if node.get('path') == target_path:
            return node
        for child in node.get('children', []):
            res = find_node(child, target_path)
            if res: return res
        return None

    print("\n" + "="*40)
    print(f"{'文件夹路径':<30} | {'数据库译名':<20} | {'UI 实际显示':<20}")
    print("-" * 80)

    for v in has_shadow[:5]:
        path = v['folder_name']
        db_shadow = v.get('shadow_name', '')
        
        node = find_node(tree, path)
        ui_shadow = node.get('shadow_name', '') if node else '节点未找到'
        
        status = "✅ 一致" if db_shadow == ui_shadow else "❌ 逻辑断裂 (数据库有但 UI 没显)"
        print(f"{os.path.basename(path):<30} | {db_shadow[:20]:<20} | {ui_shadow[:20]:<20} --> {status}")

if __name__ == "__main__":
    verify()
