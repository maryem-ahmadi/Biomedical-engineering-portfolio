import json

with open('app.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

found = False
for i, cell in enumerate(nb['cells']):
    s = ''.join(cell['source'])
    if 'device_map="auto"' in s:
        found = True
        print(f"Trouvé 'auto' dans cellule {i}")
        print(s[:300])
        print("---")

if not found:
    print("Aucune cellule avec device_map='auto'")
