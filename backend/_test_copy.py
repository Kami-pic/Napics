"""验证复制操作：多次检查文件是否出现"""
import requests, os, time, json

BASE = "http://localhost:8000"
SRC = r"\\DS218play\share\视频\动画番\测试动画合集\自由的她们\自由的她们.Libres.EP1.720p.WEBrip.中法双语.弯弯字幕组.mp4"
TGT = r"\\DS218play\share\视频\其他视频\洗版测试"
EXPECTED = os.path.join(TGT, os.path.basename(SRC))

print(f"源文件存在: {os.path.isfile(SRC)}")
print(f"目标目录存在: {os.path.isdir(TGT)}")
print(f"预期副本路径: {EXPECTED}")
print(f"副本已存在(执行前): {os.path.isfile(EXPECTED)}")

# 执行复制
r = requests.post(f"{BASE}/batch_manage", json={"action": "copy", "paths": [SRC], "target": TGT}, timeout=30)
d = r.json()
print(f"\nAPI 返回: {json.dumps(d, ensure_ascii=False)}")

# 多次检查
for wait in [0, 1, 2, 5, 10]:
    if wait > 0:
        time.sleep(wait)
    exists = os.path.isfile(EXPECTED)
    print(f"等待 {wait}s 后: 副本存在={exists}")
    if exists:
        size = os.path.getsize(EXPECTED)
        print(f"  副本大小: {size} bytes")
        break

# 清理
if os.path.isfile(EXPECTED):
    os.remove(EXPECTED)
    print("副本已清理")
else:
    # 检查目标目录内容
    print(f"\n目标目录内容:")
    for f in os.listdir(TGT):
        print(f"  {f}")
