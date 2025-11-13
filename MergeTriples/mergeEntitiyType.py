##############################################################################
## Girdi Formatı Örneği:
##   {
##      "baş": "Lamine Yamal",
##       "baş_tipi": "Kişi",
##       "ilişki": "Kazandı",
##       "uç": "La Liga 2022-23 Sezonu",
##       "uç_tipi": "Turnuva"
##   },
## Uç ya da Baş isimleri incelenerek aynı olan varlıkların tip bilgilerini toplar
## Çıktı formatından entitiy (uç ya da baş) ve entity_type (tip bilgisi) vardır
## Çıktı json adı : entity_types_analysis.json
##############################################################################
import json
from collections import defaultdict
import os

def merge_entity_types(all_data):
    """
    Tüm varlıklar için kullanılan tip bilgilerini toplar.
    Her varlık için tüm unique tiplerini birleştirir.
    """
    # Varlık adlarını gruplamak için dictionary
    entity_types = defaultdict(set)
    
    # Tüm verilerden varlık-tip çiftlerini topla
    for record in all_data:
        # Baş varlığı ve tipi
        if "baş" in record:
            entity = record["baş"]
            if "baş_tipi" in record:
                entity_types[entity].add(record["baş_tipi"])
        
        # Uç varlığı ve tipi
        if "uç" in record:
            entity = record["uç"]
            if "uç_tipi" in record:
                entity_types[entity].add(record["uç_tipi"])
    
    # Sonuçları formatla
    result = []
    for entity, types in entity_types.items():
        if types:  # Sadece tip bilgisi olan varlıkları al
            entity_record = {
                "entity": entity,
                "entity_type": ", ".join(sorted(types))
            }
            result.append(entity_record)
    
    # Entity adına göre sırala
    result.sort(key=lambda x: x["entity"])
    
    return result

def load_all_json_files():
    """
    Tüm JSON dosyalarını yükler ve birleştirir
    """
    base_path = r"c:\Users\Hp\Desktop\SDP\Wikipedia_Wikidata_compare"
    
    files_to_process = [
        "LLMWithCasualDataExample.json",
        "LLMwithWikiDataExample.json", 
        "WikiDataTriples.json"
    ]
    
    all_data = []
    total_original_records = 0
    
    for filename in files_to_process:
        file_path = os.path.join(base_path, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_data.extend(data)
                total_original_records += len(data)
                print(f"{filename}: {len(data)} kayıt yüklendi")
        
        except FileNotFoundError:
            print(f"Dosya bulunamadı: {file_path}")
        except json.JSONDecodeError:
            print(f"JSON formatı hatalı: {file_path}")
    
    return all_data, total_original_records

def main():
    print("=== Varlık Tip Analizi ===")
    
    # Tüm JSON dosyalarını yükle
    all_data, total_original = load_all_json_files()
    
    if not all_data:
        print("Hiç veri yüklenemedi!")
        return
    
    print(f"\nToplam orijinal kayıt sayısı: {total_original}")
    
    # Varlık tiplerini analiz et
    entity_type_data = merge_entity_types(all_data)
    
    print(f"Toplam unique varlık sayısı: {len(entity_type_data)}")
    
    # Sonucu JSON formatında yazdır
    print("\n=== VARLIK TİP ANALİZİ ===")
    result_json = json.dumps(entity_type_data, ensure_ascii=False, indent=2)
    print(result_json)
    
    # Sonucu dosyaya kaydet
    output_file = r"c:\Users\Hp\Desktop\SDP\Wikipedia_Wikidata_compare\entity_types_analysis.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(entity_type_data, f, ensure_ascii=False, indent=2)
    print(f"\nSonuç kaydedildi: {output_file}")

if __name__ == "__main__":
    main()