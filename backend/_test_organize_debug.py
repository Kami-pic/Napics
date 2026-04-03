"""调试测试动画合集的一键整理"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import requests

path = "\\\\DS218play\\share\\视频\\动画番\\测试动画合集"

# 测试 /organize/full dry_run
print("=== /organize/full dry_run=true ===")
r = requests.post("http://localhost:8000/organize/full",
                   params={"path": path, "dry_run": "true"}, timeout=120)
print(f"HTTP {r.status_code}")
if r.status_code == 200:
    d = r.json()
    print(f"folder_type: {d.get('folder_type')}")
    print(f"tmdb_match: {d.get('tmdb_match', {})}")
    plan = d.get('plan', [])
    print(f"plan items: {len(plan)}")
    for item in plan[:5]:
        mapped = item.get('mapped')
        if mapped:
            print(f"  {item['original_filename']} -> S{mapped['season']:02d}E{mapped['episode']:02d}")
        else:
            print(f"  {item['original_filename']} -> SKIP: {item.get('skip_reason')}")
    summary = d.get('summary', {})
    print(f"summary: {summary}")
    # 检查 wrap_plan 和 archive_plan
    print(f"wrap_plan: {len(d.get('wrap_plan', []))}")
    print(f"archive_plan: {len(d.get('archive_plan', []))}")
else:
    print(r.text[:500])
