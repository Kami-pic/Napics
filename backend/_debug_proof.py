import json
import os
import sys

# 保证能加载后端模块
sys.path.append(os.getcwd())
from main import get_library_tree

def proof_of_concept():
    # 1. 模拟当前的错误状态 (UI 获取不到译名)
    print("\n[对比实验 - 修复前]")
    tree_original = get_library_tree()
    
    def find_node(node, target_name):
        if node.get('name') == target_name: return node
        for c in node.get('children', []):
            r = find_node(c, target_name)
            if r: return r
        return None

    target = "其他地区"
    node_pre = find_node(tree_original, target)
    print(f"目标文件夹: {target}")
    print(f"当前 UI 显示的译名: '{node_pre.get('shadow_name', '')}'")

    # 2. 模拟修复后的逻辑 (从数据库中提取)
    print("\n[对比实验 - 修复后 (逻辑对齐)]")
    with open('media_library.json', 'r', encoding='utf-8') as f:
        lib = json.load(f)
    
    # 模拟架构改进：不再物理读盘，而是根据 node 下挂载的 videos 聚合信息
    if node_pre and node_pre.get('videos'):
        # 寻找该文件夹下在数据库中已有的译名
        # 在真实的修复中，我们会预先建立路径索引加速
        folder_path = node_pre['path']
        sample_video = node_pre['videos'][0]
        
        # 从数据库中寻找匹配的译名
        match = next((v for v in lib if v['file_name'] == sample_video.get('file_name')), None)
        
        if match and match.get('shadow_name'):
            node_pre['shadow_name'] = match['shadow_name']
            node_pre['shadow_tmdb_id'] = match.get('shadow_tmdb_id')
            print(f"✅ 逻辑修正成功！")
            print(f"新 UI 展示译名: '{node_pre['shadow_name']}'")
            print(f"关联 TMDB ID: {node_pre['shadow_tmdb_id']}")
        else:
            print("❌ 依然匹配失败，请检查数据库数据。")

if __name__ == "__main__":
    proof_of_concept()
