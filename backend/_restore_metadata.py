import json
import os
import re

def restore_metadata():
    lib_path = 'backend/media_library.json'
    cache_dir = 'backend/scrape_cache'
    
    if not os.path.exists(lib_path) or not os.path.exists(cache_dir):
        print("❌ 核心路径缺失")
        return

    # 1. 建立缓存索引 (标题/原始名 -> 详情)
    title_to_id = {}
    print(f"[*] 正在分析 {len(os.listdir(cache_dir))} 个缓存文件...")
    
    for filename in os.listdir(cache_dir):
        if not filename.endswith('.json'): continue
        try:
            with open(os.path.join(cache_dir, filename), 'r', encoding='utf-8') as f:
                data = json.load(f)
                tmdb_id = data.get('tmdb_id')
                if tmdb_id:
                    # 索引原名和标题
                    if data.get('original_title'):
                        title_to_id[data['original_title'].lower()] = tmdb_id
                    if data.get('title'):
                        title_to_id[data['title'].lower()] = tmdb_id
                    if data.get('name'): # TV 剧集名
                        title_to_id[data['name'].lower()] = tmdb_id
        except:
            continue

    # 2. 注入媒体库
    with open(lib_path, 'r', encoding='utf-8') as f:
        lib = json.load(f)

    restored_count = 0
    for v in lib:
        # 如果 ID 丢失了，尝试通过影子名找回
        if not v.get('shadow_tmdb_id'):
            shadow = v.get('shadow_name', '')
            if shadow:
                # 尝试从影子名中提取纯净标题进行匹配
                # 如: "你妈妈也一样 And Your Mother Too (2001)" -> "And Your Mother Too"
                clean_shadow = re.sub(r'\(\d{4}\)', '', shadow).strip().lower()
                
                # 尝试直接匹配或分词匹配
                matched_id = None
                if clean_shadow in title_to_id:
                    matched_id = title_to_id[clean_shadow]
                else:
                    # 尝试匹配影子名中的各个部分
                    for part in re.split(r'\s{2,}|/|·', clean_shadow):
                        p = part.strip()
                        if p in title_to_id:
                            matched_id = title_to_id[p]
                            break
                
                if matched_id:
                    v['shadow_tmdb_id'] = matched_id
                    v['has_poster'] = True
                    restored_count += 1

    if restored_count > 0:
        with open(lib_path, 'w', encoding='utf-8') as f:
            json.dump(lib, f, indent=4, ensure_ascii=False)
        print(f"✅ 刮削元数据找回手术完成！成功复原 {restored_count} 条记录的 TMDB ID 和封面状态。")
    else:
        print("💡 没有发现可匹配的元数据。")

if __name__ == "__main__":
    restore_metadata()
