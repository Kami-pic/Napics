"""用真实 NAS 数据测试清洗名效果"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import requests

# 调 API 拿树
r = requests.get("http://localhost:8000/library/tree", timeout=30)
tree = r.json()

def walk(node, depth=0, parent_clean=""):
    ft = node.get("folder_type", "")
    cn = node.get("clean_name", "")
    sn = node.get("shadow_name", "")
    name = node.get("name", "")
    
    if ft in ("tv", "season") and depth >= 2:
        label = "📺" if ft == "tv" else "📂"
        print(f"{'  ' * depth}{label} {name}")
        print(f"{'  ' * depth}   clean_name: {cn}")
        if sn:
            print(f"{'  ' * depth}   shadow_name: {sn}")
        
        # 显示前 3 个视频的 clean_name
        for v in node.get("videos", [])[:3]:
            vc = v.get("clean_name", "")
            vf = v.get("file_name", "")
            print(f"{'  ' * depth}   🎬 {vf[:50]}")
            print(f"{'  ' * depth}      clean: {vc}")
    
    for child in node.get("children", []):
        walk(child, depth + 1, cn)

# 只看几个有代表性的
targets = ["西部世界", "切尔诺贝利", "钢之炼金术师", "混沌武士", "火线", "进击的巨人", "守望"]

for cat in tree.get("children", []):
    for folder in cat.get("children", []):
        if any(t in folder.get("name", "") for t in targets):
            print(f"\n{'='*60}")
            print(f"📁 {cat['name']} / {folder['name']}")
            print(f"   clean_name: {folder.get('clean_name', '')}")
            print(f"   folder_type: {folder.get('folder_type', '')}")
            walk(folder, depth=2)
