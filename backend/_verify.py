import os, requests, json, time
BASE = "http://localhost:8000"

vid = r"\\DS218play\share\视频\电影\测试文件夹\爱乐之城 La La Land (2016)\爱乐之城 La La Land (2016) 720p.mp4"
folder = r"\\DS218play\share\视频\电影\测试文件夹\爱乐之城 La La Land (2016)"

print("=== 状态检查 ===")
print(f"视频存在: {os.path.isfile(vid)}")
print(f"文件夹存在: {os.path.isdir(folder)}")
if os.path.isdir(folder):
    print(f"文件夹内容: {os.listdir(folder)}")

print("\n=== 测试改名（只改视频文件）===")
new_name = "test_rename_video.mp4"
r = requests.post(f"{BASE}/rename", params={"old_path": vid, "new_name": new_name}, timeout=15)
d = r.json()
print(f"API 返回: {json.dumps(d, ensure_ascii=False)}")
time.sleep(1)

# 检查结果
new_vid = os.path.join(folder, new_name)
print(f"新文件存在: {os.path.isfile(new_vid)}")
print(f"旧文件存在: {os.path.isfile(vid)}")
print(f"文件夹仍在: {os.path.isdir(folder)}")
if os.path.isdir(folder):
    print(f"文件夹内容: {os.listdir(folder)}")

# 回退
if os.path.isfile(new_vid):
    old_name = "爱乐之城 La La Land (2016) 720p.mp4"
    r = requests.post(f"{BASE}/rename", params={"old_path": new_vid, "new_name": old_name}, timeout=15)
    print(f"回退: {r.json()}")
    time.sleep(1)
    print(f"恢复后视频存在: {os.path.isfile(vid)}")
