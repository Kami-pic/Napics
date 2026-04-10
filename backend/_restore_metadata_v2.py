import json
import os
import re

def restore_metadata():
    lib_path = 'media_library.json'
    cache_dir = 'scrape_cache'
    
    if not os.path.exists(lib_path):
        print(f"❌ 错误: 找不到库文件 {lib_path}")
        return
    if not os.path.exists(cache_dir):
        print(f"❌ 错误: 找不到缓存目录 {cache_dir}")
        return

    # 1. 建立缓存快速索引 (原标题/中文名 -> TMDB_ID)
    title_to_id = {}
    print(f"[*] 正在分析 {len(os.listdir(cache_dir))} 个缓存文件...")
    
    for filename in os.listdir(cache_dir):
        if not filename.endswith('.json'): continue
        try:
            with open(os.path.join(cache_dir, filename), 'r', encoding='utf-8') as f:
                data = json.load(f)
                tmdb_id = data.get('tmdb_id')
                if not tmdb_id: continue
                
                # 收集所有可能的标题用于匹配
                keys = []
                if data.get('title'): keys.append(data['title'].lower())
                if data.get('original_title'): keys.append(data['original_title'].lower())
                if data.get('name'): keys.append(data['name'].lower())
                
                for k in keys:
                    title_to_id[k] = tmdb_id
        except:
            continue

    # 2. 注入媒体库
    with open(lib_path, 'r', encoding='utf-8') as f:
        lib = json.load(f)

    restored_count = 0
    for v in lib:
        # 即使已经有 ID，也强制更新一次 has_poster 状态
        shadow = v.get('shadow_name', '')
        if not shadow: continue
        
        # 清洗影子名 (去括号、去多余空格)
        clean_shadow = re.sub(r'\(\d{4}\)', '', shadow).strip().lower()
        
        matched_id = None
        # 策略 A: 直接匹配
        if clean_shadow in title_to_id:
            matched_id = title_to_id[clean_shadow]
        else:
            # 策略 B: 拆分匹配 (处理 "译名 原名" 格式)
            parts = re.split(r'\s{2,}|/|·', clean_shadow)
            for p in parts:
                p_clean = p.strip()
                if p_clean in title_to_id:
                    matched_id = title_to_id[p_clean]
                    break
        
        if matched_id:
            v['shadow_tmdb_id'] = matched_id
            v['has_poster'] = True
            restored_count += 1

    if restored_count > 0:
        with open(lib_path, 'w', encoding='utf-8') as f:
            json.dump(lib, f, indent=4, ensure_ascii=False)
        print(f"✅ 完成！成功从缓存中追回了 {restored_count} 条记录的元数据。")
    else:
        print("💡 库文件已处于最新状态或未发现匹配条目。")

if __name__ == "__main__":
    restore_metadata()
