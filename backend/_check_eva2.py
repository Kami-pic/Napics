import sys, os
sys.path.insert(0, '.')
import organizer, config_manager
config_m = config_manager.ConfigManager()
library = config_m.load_library()
p = r"\\DS218play\share\视频\动画电影\福音战士新剧场版 Evangelion 三部曲"

ct = organizer.classify_folder(p, library)
print(f"classify type: {ct['type']}")

from organizer import _is_season_dir, _is_series_collection
print("\n季目录判定:")
subdirs = [d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))]
for d in subdirs:
    print(f"  _is_season_dir: {_is_season_dir(d)} <- {d[:40]}")
print(f"\n_is_series_collection: {_is_series_collection(subdirs, os.path.basename(p))}")
