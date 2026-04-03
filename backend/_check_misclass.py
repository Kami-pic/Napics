import json
with open('_batch_steps234_report.json', encoding='utf-8') as f:
    r = json.load(f)
print("=== series_collection / movie_collection ===")
for item in r['results']:
    ft = item.get('folder_type','')
    if ft in ('series_collection','movie_collection'):
        cat = item['category']
        name = item['name']
        moves = item.get('move_ops', 0)
        print(f"  [{cat}] {name}: {ft} (moves={moves})")

print("\n=== movie_aggregate ===")
for item in r['results']:
    ft = item.get('folder_type','')
    if ft == 'movie_aggregate':
        print(f"  [{item['category']}] {item['name']}: {ft}")
