import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import requests

path = "\\\\DS218play\\share\\视频\\电视剧\\兄弟连"
r = requests.post("http://localhost:8000/organize/structure",
                   params={"path": path, "dry_run": "true"}, timeout=30)
d = r.json()
print(f"HTTP {r.status_code}, count={d.get('count', 0)}")
for op in d.get("ops", [])[:5]:
    print(f"  {op.get('action')} | {op.get('desc', '')}")
