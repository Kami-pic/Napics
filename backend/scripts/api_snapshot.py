import requests
import json
import logging
import os
import sys

logger = logging.getLogger(__name__)
# 假设后端运行在 8000 端口
BASE_URL = "http://127.0.0.1:8000"
SNAPSHOT_DIR = "refactor_snapshots"

ENDPOINTS = [
    "/library",
    "/library/tree",
    "/alist/mounts",
    # 可以添加更多
]

def capture_snapshots():
    if not os.path.exists(SNAPSHOT_DIR):
        os.makedirs(SNAPSHOT_DIR)
    
    for ep in ENDPOINTS:
        try:
            url = f"{BASE_URL}{ep}"
            logger.info(f"Capturing {url}...")
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                name = ep.strip("/").replace("/", "_") or "root"
                with open(os.path.join(SNAPSHOT_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
                    json.dump(resp.json(), f, indent=2, ensure_ascii=False)
            else:
                logger.error(f"Failed {url}: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error {url}: {e}")

def compare_snapshots():
    # 重构后运行，对比当前 API 响应与 snapshot
    diffs = 0
    for ep in ENDPOINTS:
        name = ep.strip("/").replace("/", "_") or "root"
        snapshot_file = os.path.join(SNAPSHOT_DIR, f"{name}.json")
        if not os.path.exists(snapshot_file):
            continue
            
        with open(snapshot_file, "r", encoding="utf-8") as f:
            old_data = json.load(f)
            
        try:
            url = f"{BASE_URL}{ep}"
            new_data = requests.get(url, timeout=10).json()
            
            if old_data != new_data:
                logger.info(f"DIFF DETECTED in {ep}!")
                diffs += 1
            else:
                logger.info(f"PASS: {ep}")
        except Exception as e:
            logger.error(f"Error comparing {ep}: {e}")
            diffs += 1
    
    return diffs

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        res = compare_snapshots()
        sys.exit(res)
    else:
        capture_snapshots()
