import json
pages, total = set(), 0
with open("paragraph_dataset.jsonl", encoding="utf-8") as f:
    for line in f:
        total += 1
        pages.add(json.loads(line)["wikipedia_page"])
print(f"Toplam paragraf: {total}")
print(f"Benzersiz sayfa (madde) sayısı: {len(pages)}")