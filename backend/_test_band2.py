import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import requests

# 1. NAS 物理结构
path = "\\\\DS218play\\share\\视频\\电视剧\\兄弟连"
print("=== NAS 物理结构 ===")
for item in sorted(os.listdir(path)):
    fp = os.path.join(path, item)
    if os.path.isdir(fp):
        vids = [f for f in os.listdir(fp) if os.path.splitext(f)[1].lower() in {'.mp4','.mkv'}]
        nfos = [f for f in os.listdir(fp) if f.endswith('.nfo')]
        print(f"  [DIR] {item}/ ({len(vids)} 视频, {len(nfos)} NFO)")
        for v in vids[:3]:
            print(f"    {v}")
        if len(vids) > 3:
            print(f"    ... 共 {len(vids)} 个")
    else:
        print(f"  {item}")

# 2. 后端树结构
print("\n=== 后端树结构 ===")
r = requests.get("http://localhost:8000/library/tree", timeout=30)
tree = r.json()

def find_node(node, name):
    if name in node.get("name", ""):
        return node
    for c in node.get("children", []):
        found = find_node(c, name)
        if found:
            return found
    return None

band = find_node(tree, "兄弟连")
if band:
    print(f"name: {band['name']}")
    print(f"folder_type: {band.get('folder_type')}")
    print(f"clean_name: {band.get('clean_name')}")
    print(f"shadow_name: {band.get('shadow_name')}")
    print(f"video_count: {band.get('video_count')}")
    print(f"直接视频: {len(band.get('videos', []))}")
    print(f"子目录: {len(band.get('children', []))}")
    for c in band.get("children", []):
        print(f"  [子] {c['name']} type={c.get('folder_type')} clean={c.get('clean_name')} vids={len(c.get('videos',[]))}")
        for v in c.get("videos", [])[:2]:
            print(f"    🎬 {v['file_name'][:50]} clean={v.get('clean_name','')}")
else:
    print("未找到兄弟连节点")
