import requests
path = "\\\\DS218play\\share\\视频\\电视剧\\切尔诺贝利S1"
r = requests.post("http://localhost:8000/organize/structure",
                   params={"path": path, "dry_run": "true"}, timeout=30)
print(f"HTTP {r.status_code}")
d = r.json()
print(f"count={d.get('count', 0)}")
for o in d.get("ops", [])[:3]:
    print(f"  {o.get('desc', '')}")
