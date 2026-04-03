"""测试标准结构按钮的降级逻辑"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import organizer

path = "\\\\DS218play\\share\\视频\\动画番\\钢之炼金术师FA"

# 1. NFO 归位（应该返回空，因为没有 episode.nfo）
r1 = organizer.reorganize_seasons_by_nfo(path, dry_run=True)
print(f"NFO 归位 ops: {len(r1.get('ops', []))}")

# 2. 正则降级归位（应该返回 63 个 move）
r2 = organizer.reorganize_seasons(path, dry_run=True, category_hint="tv")
print(f"正则降级 ops: {len(r2.get('ops', []))}")

# 3. 模拟 organize_structure 的完整逻辑
total_ops = []
reorg = organizer.reorganize_seasons_by_nfo(path, dry_run=True)
if reorg.get("ops"):
    total_ops.extend(reorg["ops"])
    print("走 NFO 路径")
else:
    reorg_fb = organizer.reorganize_seasons(path, tmdb_client=None, dry_run=True, category_hint="tv")
    if reorg_fb.get("ops"):
        total_ops.extend(reorg_fb["ops"])
        print("走正则降级路径")
    else:
        print("两个路径都没有 ops")

print(f"最终 ops: {len(total_ops)}")
if total_ops:
    print(f"  第一个: {total_ops[0].get('action')} {os.path.basename(total_ops[0].get('old',''))}")
