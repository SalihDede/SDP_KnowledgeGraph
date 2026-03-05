import json
import sys

with open(sys.argv[1], 'r', encoding='utf-8') as f:
    data = json.load(f)
    
    # Unique entity'leri topla (baş ve uç'ları aynı set'te)
    entitiler = set()
    for item in data:
        entitiler.add(item['baş'])
        entitiler.add(item['uç'])
    
    # Unique ilişkileri topla
    iliskiler = set()
    for item in data:
        iliskiler.add(item['ilişki'])
    
    print(f"Toplam kayıt sayısı: {len(data)}")
    print(f"Unique entity sayısı: {len(entitiler)}")
    print(f"Unique ilişki sayısı: {len(iliskiler)}")