"""测试 _is_series_collection 对子文件夹名的判定"""
import sys
sys.path.insert(0, '.')
from organizer import _is_series_collection

tests = [
    # (子文件夹名列表, 父文件夹名, 期望结果)
    # 系列电影
    (["哥斯拉：决战之都 Godzilla City on the Edge of Battle (2018)",
      "哥斯拉：噬星者 GODZILLA 星を喰う者 (2018)",
      "哥斯拉：怪兽行星 GODZILLA 怪獣惑星 (2017)"],
     "哥斯拉动画电影", True),
    
    (["壳中少女：压缩 Mardock Scramble The First Compression (2010)",
      "壳中少女：排气 Mardock Scramble The Third Exhaust (2012)",
      "壳中少女：燃烧 Mardock Scramble The Second Combustion (2011)"],
     "壳中少女 Mardock Scramble", True),
    
    (["福音战士新剧场版：Q Evangelion 3 0 You Can (Not) Redo (2012)",
      "福音战士新剧场版：序 Evangelion 1 0 You Are (Not) Alone (2007)",
      "福音战士新剧场版：破 Evangelion 2 0 You Can (Not) Advance (2009)",
      "福音战士新剧场版：终 Evangelion 3 0+1 0 Thrice Upon a Time (2021)"],
     "福音战士新剧场版 Evangelion 三部曲", True),
    
    # 非系列（不同电影的合集）
    (["007 无暇赴死", "Dogman 2023", "Her 2013"],
     "电影", False),
]

for names, parent, expected in tests:
    result = _is_series_collection(names, parent)
    status = "✓" if result == expected else "✗"
    print(f"  {status} {parent}: {'series' if result else 'not series'} (期望 {'series' if expected else 'not series'})")
    if result != expected:
        print(f"    子文件夹: {names[:2]}")
