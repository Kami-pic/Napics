import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import organizer
path = "\\\\DS218play\\share\\视频\\电视剧\\切尔诺贝利S1"
r = organizer.reorganize_seasons_by_nfo(path, dry_run=True)
for op in r.get("ops", []):
    print(f"{op.get('action')} | {op.get('desc', '')}")
