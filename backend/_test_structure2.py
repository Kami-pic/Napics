"""测试切尔诺贝利和守望尘世的标准结构"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import main

# 切尔诺贝利
path1 = "\\\\DS218play\\share\\视频\\电视剧\\切尔诺贝利S1"
print("=== 切尔诺贝利S1 (organize_structure API) ===")
try:
    result = main.organize_structure(path=path1, dry_run=True)
    print(f"status={result['status']}, count={result['count']}")
    for op in result['ops'][:5]:
        print(f"  {op.get('desc', op.get('action',''))}")
    if result['count'] > 5:
        print(f"  ... 还有 {result['count'] - 5} 项")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()

print()

# 守望尘世
path2 = "\\\\DS218play\\share\\视频\\电视剧\\守望尘世S1"
print("=== 守望尘世S1 (organize_structure API) ===")
try:
    result = main.organize_structure(path=path2, dry_run=True)
    print(f"status={result['status']}, count={result['count']}")
    for op in result['ops'][:5]:
        print(f"  {op.get('desc', op.get('action',''))}")
    if result['count'] > 5:
        print(f"  ... 还有 {result['count'] - 5} 项")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
