import json
import os
import sys

# 注入 backend 目录
sys.path.append(os.getcwd())

from analyzer import analyze_folder
from config_manager import ConfigManager
from analysis_cache import AnalysisCache

def repopulate_cache():
    cm = ConfigManager()
    config = cm.config
    library = cm.load_library()
    cache = AnalysisCache()
    
    # 获取已在库中的文件夹路径集合 (加速查找)
    existing_folders = {v['folder_name'] for v in library}
    
    # 扫描的所有 NAS 路径
    base_paths = config.nas_paths if config.nas_paths else [config.nas_path]
    categories = ["电影", "纪录片", "剧集", "其他视频"]
    
    print(f"[*] 正在扫描 {base_paths} 以寻找失踪的新影片...")
    
    newly_discovered = 0
    for base_path in base_paths:
        for cat in categories:
            cat_path = os.path.join(base_path, cat)
            if not os.path.exists(cat_path): continue
            
            # 遍历一级分类下的所有子文件夹
            try:
                folders = [f for f in os.listdir(cat_path) if os.path.isdir(os.path.join(cat_path, f))]
                for f in folders:
                    full_path = os.path.join(cat_path, f)
                    
                    # 如果这个文件夹不在数据库中，说明是“新发现”
                    if full_path not in existing_folders:
                        print(f"发现新影片: {f}")
                        # 调用分析器进行识别，并存入缓存
                        report = analyze_folder(full_path, library, category_hint=cat)
                        if report:
                            cache.update_folder(full_path, report)
                            newly_discovered += 1
            except Exception as e:
                print(f"扫描 {cat} 失败: {e}")

    print(f"✅ 缓存重建完成！重新找回了 {newly_discovered} 个待整理的新影片记录。")

if __name__ == "__main__":
    repopulate_cache()
