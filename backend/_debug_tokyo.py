import sys, os; sys.path.insert(0, '.')
from organizer import _is_season_dir, _extract_season_number, classify_folder
import config_manager

config_m = config_manager.ConfigManager()
library = config_m.load_library()
p = r"\\DS218play\share\视频\动画番\东京食尸鬼 Tokyo Ghoul"

print("子文件夹:")
for d in sorted(os.listdir(p)):
    dp = os.path.join(p, d)
    if os.path.isdir(dp):
        is_s = _is_season_dir(d)
        s_num = _extract_season_number(d)
        print(f"  '{d}' -> is_season={is_s} season_num={s_num}")

ct = classify_folder(p, library)
print(f"\nclassify: {ct['type']}")
