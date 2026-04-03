import sys, os, re; sys.path.insert(0, '.')

# 手动执行 parse_filename 的尾部提取逻辑
name = os.path.splitext("【更多美剧请去www.dy131.com】冰与火之歌：权力的游戏第一季1024高清02.rmvb")[0]
print(f"name: {name}")
print(f"name[-5:]: {name[-5:]}")

# 测试正则
tail_ep = re.search(r'(?:^|[^\d])(\d{1,2})$', name)
print(f"tail_ep: {tail_ep}")
if tail_ep:
    print(f"  group(1): {tail_ep.group(1)}")

# 也测试 splitext
print(f"\nsplitext: {os.path.splitext(name)}")
