import requests, json
for n in range(1,501):
    try:
        r = requests.get(f'http://127.0.0.1:8000/sankhya/item/list/?nunota={n}', timeout=1)
        j = r.json()
        if j.get('ok') and j.get('items'):
            print('FOUND', n, len(j['items']))
            print(json.dumps(j['items'][0], ensure_ascii=False, indent=2))
            break
    except Exception:
        pass
print('done')
