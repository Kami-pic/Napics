"""回滚所有改名操作（按时间从新到旧）"""
import urllib.request
import urllib.parse
import json
import os
import time

snap_dir = "organize_snapshots"
files = sorted([f for f in os.listdir(snap_dir) if f.startswith("snapshot_")], reverse=True)

rename_snapshots = []
for fname in files:
    with open(os.path.join(snap_dir, fname), "r", encoding="utf-8") as f:
        data = json.load(f)
    ops = data.get("ops", [])
    if not ops:
        continue
    # 判断是否是改名操作（大部分 old 和 new 在同一目录下）
    rename_count = sum(1 for op in ops if os.path.dirname(op.get("old_path","")) == os.path.dirname(op.get("new_path","")))
    if rename_count > len(ops) * 0.5:
        rename_snapshots.append(data)

print(f"找到 {len(rename_snapshots)} 个改名快照，准备回滚...\n")

success_count = 0
fail_count = 0

for snap in rename_snapshots:
    sid = snap["id"]
    ops_count = len(snap.get("ops", []))
    sample = os.path.basename(snap["ops"][0].get("new_path", ""))[:30] if snap["ops"] else ""
    
    try:
        url = f"http://localhost:8000/organize/rollback?snapshot_id={sid}"
        req = urllib.request.Request(url, method="POST", data=b"")
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read().decode("utf-8"))
        
        s = len(result.get("success", []))
        f = len(result.get("failed", []))
        print(f"  ✓ [{sid}] {ops_count} ops, success={s}, failed={f} ({sample}...)")
        success_count += 1
    except Exception as e:
        print(f"  ✗ [{sid}] Error: {e}")
        fail_count += 1
    
    time.sleep(0.1)

print(f"\n回滚完成: {success_count} 成功, {fail_count} 失败")
