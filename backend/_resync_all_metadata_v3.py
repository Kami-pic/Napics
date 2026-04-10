import json
import os
import re
import xml.etree.ElementTree as ET

def resync_all():
    lib_path = 'media_library.json'
    if not os.path.exists(lib_path):
        print("❌ 错误: 找不到库文件。")
        return

    with open(lib_path, 'r', encoding='utf-8') as f:
        lib = json.load(f)

    print(f"[*] 正在为 {len(lib)} 条记录找回元数据...")
    updated = 0

    for v in lib:
        fp = v.get('file_path', '')
        if not fp: continue
        
        # 寻找 NFO 文件 (多种可能的名字)
        dir_path = os.path.dirname(fp)
        nfo_candidates = [
            os.path.join(dir_path, 'movie.nfo'),
            os.path.join(dir_path, 'tvshow.nfo'),
            os.path.splitext(fp)[0] + '.nfo'
        ]
        
        found_nfo = False
        for nfo in nfo_candidates:
            if os.path.exists(nfo):
                try:
                    # 解析 NFO 提取 TMDB ID 和标题
                    tree = ET.parse(nfo)
                    root = tree.getroot()
                    tmdbid = root.findtext('tmdbid') or root.findtext('uniqueid[@type="tmdb"]')
                    title = root.findtext('title')
                    
                    if tmdbid:
                        v['shadow_tmdb_id'] = tmdbid
                        v['has_poster'] = True
                        if title: v['shadow_name'] = title
                        updated += 1
                        found_nfo = True
                        break
                except :
                    continue
        
        # 如果没找到 NFO，但 shadow_name 为空，尝试通过文件名清洗出一个影子名
        if not v.get('shadow_name'):
            from analyzer import _clean_filename_for_folder
            v['shadow_name'] = _clean_filename_for_folder(os.path.basename(fp))

    with open(lib_path, 'w', encoding='utf-8') as f:
        json.dump(lib, f, indent=4, ensure_ascii=False)
    
    print(f"✅ 元数据找回手术完成！已通过物理扫描补完 {updated} 条关键元数据。")

if __name__ == "__main__":
    resync_all()
