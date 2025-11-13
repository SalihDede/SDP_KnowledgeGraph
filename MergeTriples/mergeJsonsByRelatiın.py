##############################################################################
## Girdi Formatı Örneği:
##   {
##      "baş": "Lamine Yamal",
##       "baş_tipi": "Kişi",
##       "ilişki": "Kazandı",
##       "uç": "La Liga 2022-23 Sezonu",
##       "uç_tipi": "Turnuva"
##   },
## Uç ve Baş isimleri aynı olan KG 3'lülerini realtion bazlı birleştirir
## Çıktı formatından uç baş ve relation vardır
## Çıktı json adı : merged_all_relations.json
##############################################################################
import json
from collections import defaultdict
import os

def merge_all_json_relations(all_data):
    """
    Tüm JSON verilerini birleştirip aynı baş ve uç değerlerine sahip kayıtları birleştirir.
    İlişkilerde tekrar olmasını önler (unique).
    """
    # Baş-Uç çiftlerini gruplamak için dictionary
    grouped = defaultdict(list)
    
    # Tüm verilerden baş-uç çiftlerini grupla
    for record in all_data:
        key = (record["baş"], record["uç"])
        grouped[key].append(record)
    
    # Birleştirilmiş sonuçları tutacak liste
    merged_results = []
    
    for (baş, uç), records in grouped.items():
        # Sadece baş, uç ve ilişki alanlarını tut
        merged_record = {
            "baş": baş,
            "uç": uç
        }
        
        # İlişkileri topla ve unique yap
        relations_set = set()
        for record in records:
            relations_set.add(record["ilişki"])
        
        # İlişkileri virgülle ayırarak birleştir (unique ve sıralı)
        merged_record["ilişki"] = ", ".join(sorted(relations_set))
        
        merged_results.append(merged_record)
    
    return merged_results

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
    print("=== Tüm JSON dosyaları birleştiriliyor ===")
    
    # Tüm JSON dosyalarını yükle
    all_data, total_original = load_all_json_files()
    
    if not all_data:
        print("Hiç veri yüklenemedi!")
        return
    
    print(f"\nToplam orijinal kayıt sayısı: {total_original}")
    
    # Tüm veriyi birleştir
    merged_data = merge_all_json_relations(all_data)
    
    print(f"Birleştirilen kayıt sayısı: {len(merged_data)}")
    print(f"Azalma: {total_original - len(merged_data)} kayıt")
    
    # Sonucu JSON formatında yazdır
    print("\n=== BİRLEŞTİRİLMİŞ SONUÇ ===")
    result_json = json.dumps(merged_data, ensure_ascii=False, indent=2)
    print(result_json)
    
    # Sonucu dosyaya kaydet
    output_file = r"c:\Users\Hp\Desktop\SDP\Wikipedia_Wikidata_compare\merged_all_relations.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)
    print(f"\nSonuç kaydedildi: {output_file}")

if __name__ == "__main__":
    main()