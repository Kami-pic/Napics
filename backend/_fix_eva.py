import os
p = r"\\DS218play\share\视频\动画电影\福音战士新剧场版 Evangelion 三部曲"
# 删除父文件夹里的同名NFO（这些是之前测试的残留）
for f in os.listdir(p):
    if f.endswith('.nfo') and os.path.isfile(os.path.join(p, f)):
        os.remove(os.path.join(p, f))
        print(f"删除: {f}")
