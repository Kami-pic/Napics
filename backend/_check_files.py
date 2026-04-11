import os

# 检查洗版测试目录
target = r"\\DS218play\share\视频\其他视频\洗版测试"
print("洗版测试目录:")
for f in os.listdir(target):
    fp = os.path.join(target, f)
    tag = "[D]" if os.path.isdir(fp) else "[F]"
    print(f"  {tag} {f}")

print()

# 检查测试文件夹
parent = r"\\DS218play\share\视频\电影\测试文件夹"
print("测试文件夹目录:")
for f in os.listdir(parent):
    fp = os.path.join(parent, f)
    tag = "[D]" if os.path.isdir(fp) else "[F]"
    print(f"  {tag} {f}")
    if os.path.isdir(fp):
        for sf in os.listdir(fp)[:5]:
            print(f"      {sf}")
