import os
import logging
import json
import sys

# 注入 backend 路径到 sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from scraper import read_video_nfo, get_local_poster_path

logger = logging.getLogger(__name__)
def force_repair():
    cm = ConfigManager()
    library = cm.load_library()
    logger.info(f"Starting repair for {len(library)} items...")
    
    repaired_count = 0
    poster_count = 0
    
    for i, item in enumerate(library):
        path = item.get("file_path")
        if not path or not os.path.exists(path):
            continue
            
        # 1. 修复 NFO 数据 (简介、评分等)
        nfo_data = read_video_nfo(path)
        if nfo_data:
            # 只有在数据缺失或大幅更新时才写入
            if not item.get("overview") or nfo_data.get("overview") != item.get("overview"):
                item.update({
                    "title": nfo_data.get("title") or item.get("title"),
                    "overview": nfo_data.get("overview"),
                    "rating": nfo_data.get("rating"),
                    "year": nfo_data.get("year"),
                    "genre": nfo_data.get("genre")
                })
                repaired_count += 1
                
        # 2. 修复海报路径
        poster_path = get_local_poster_path(path)
        if poster_path:
            # 记录相对路径或标记
            item["poster"] = "local" 
            poster_count += 1
            
        if i % 100 == 0:
            logger.info(f"Processed {i}/{len(library)} items...")

    logger.info(f"Repair complete. Metadata updated: {repaired_count}, Posters found: {poster_count}")
    cm.save_library(library)

if __name__ == "__main__":
    force_repair()
