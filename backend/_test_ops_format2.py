import requests
path = "\\\\DS218play\\share\\视频\\电视剧\\切尔诺贝利S1"
r = requests.post("http://localhost:8000/organize/structure",
                   params={"path": path, "dry_run": "true"}, timeout=30)
d = r.json()
for op in d.get("ops", []):
    print(f"{op.get('action', '')} | {op.get('desc', '')}")
