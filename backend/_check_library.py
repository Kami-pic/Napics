"""检查 media_library.json 里关键条目的 folder_name 字段"""
import json

with open('media_library.json', encoding='utf-8') as f:
    lib = json.load(f)

targets = ['千年女优', '007：无暇', '冰菓', '冰与火之歌', '冰火S1', '阿基拉', '千与千寻']
seen = set()

for v in lib:
    fp = v.get('file_path', '')
    fn = v.get('folder_name', '')
    for t in targets:
        if t in fp and t not in seen:
            seen.add(t)
            print(f"=== {t} ===")
            print(f"  file_path:   {fp[-70:]}")
            print(f"  folder_name: {fn}")
            print(f"  file_name:   {v.get('file_name', '')}")
            print(f"  shadow_name: {v.get('shadow_name', '')}")
            print()
            break

print(f"\n总条目数: {len(lib)}")
