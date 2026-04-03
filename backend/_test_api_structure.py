"""测试 /organize/structure API"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import main

path = "\\\\DS218play\\share\\视频\\动画番\\钢之炼金术师FA"
try:
    result = main.organize_structure(path=path, dry_run=True)
    print(f"status={result['status']}, count={result['count']}")
    for op in result['ops'][:3]:
        print(f"  {op.get('action')} {op.get('desc','')}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
