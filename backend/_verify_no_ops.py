import sys, os
sys.path.insert(0, '.')
import analyzer, config_manager

cm = config_manager.ConfigManager()
lib = cm.load_library()
NAS = r"\\DS218play\share\视频"

for cat, name in [("电视剧","我的阿勒泰.2160p"), ("电视剧","逆局"), ("动画番","永生之酒 Baccano!")]:
    fp = os.path.join(NAS, cat, name)
    report = analyzer.analyze_folder(fp, lib)
    ft = report.get('folder_type', '')
    ops = report.get('structure_ops', [])
    print(f"{name}: type={ft} struct_ops={len(ops)}")
    for op in ops[:5]:
        print(f"  {op.get('action')}: {op.get('desc','')[:60]}")
