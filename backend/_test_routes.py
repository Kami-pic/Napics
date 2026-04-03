import requests
r = requests.post('http://localhost:8000/organize/full', params={'path': 'test', 'dry_run': 'true'}, timeout=5)
print(f'full: {r.status_code} {r.text[:200]}')
r2 = requests.post('http://localhost:8000/organize/structure', params={'path': 'test', 'dry_run': 'true'}, timeout=5)
print(f'structure: {r2.status_code} {r2.text[:200]}')
