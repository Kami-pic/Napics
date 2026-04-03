"""搜索丢失的第1集文件"""
import os

NAS = r"\\DS218play\share\视频"
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

# 搜索关键词
searches = {
    "我的阿勒泰": "01.2160p",
    "真探": "真探第一季01",
    "逆局": "01.1080p.HD国语中字",
    "名姝": "名姝s1 (1)",
    "UN-GO": "UN-GO (1)",
}

print("搜索丢失的第1集...\n")
for name, keyword in searches.items():
    found = []
    for root, dirs, files in os.walk(NAS):
        for f in files:
            if keyword.lower() in f.lower():
                found.append(os.path.join(root, f))
    if found:
        print(f"{name}: 找到 {len(found)} 个匹配")
        for f in found:
            print(f"  {f}")
    else:
        print(f"{name}: 未找到 '{keyword}'")
    print()
