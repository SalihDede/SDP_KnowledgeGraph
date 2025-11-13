##############################################################################
## Bu dosya mergeEntitiyType, mergeJsonsByrelaiton, ve mergeJsonByRelationAndTypes
## dosyalarını sırayla uygular ve sonucu mergedformOfAboveTriples.json dosyasına kaydeder
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

def merge_json_relations(all_data):
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

def merge_json_with_types(all_data):
    """
    Tüm JSON verilerini birleştirip aynı baş ve uç değerlerine sahip kayıtları birleştirir.
    İlişkilerde, baş_tipi ve uç_tipi'nde tekrar olmasını önler (unique).
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
        # İlişkileri topla ve unique yap
        relations_set = set()
        baş_tipi_set = set()
        uç_tipi_set = set()
        
        for record in records:
            relations_set.add(record["ilişki"])
            
            # baş_tipi ve uç_tipi varsa ekle
            if "baş_tipi" in record:
                baş_tipi_set.add(record["baş_tipi"])
            if "uç_tipi" in record:
                uç_tipi_set.add(record["uç_tipi"])
        
        # Sıralı şekilde merged_record oluştur
        merged_record = {
            "baş": baş
        }
        
        # baş_tipi varsa ekle
        if baş_tipi_set:
            merged_record["baş_tipi"] = ", ".join(sorted(baş_tipi_set))
        
        # İlişkileri virgülle ayırarak birleştir (unique ve sıralı)
        merged_record["ilişki"] = ", ".join(sorted(relations_set))
        
        # uç ekle
        merged_record["uç"] = uç
        
        # uç_tipi varsa ekle
        if uç_tipi_set:
            merged_record["uç_tipi"] = ", ".join(sorted(uç_tipi_set))
        
        merged_results.append(merged_record)
    
    return merged_results

def get_user_input():
    """
    Kullanıcıdan JSON dosyalarının konumunu sor (aynı yerde çıktı da oluşturulacak)
    """
    print("=== JSON Dosyalarının Konumu ===")
    base_path = input("JSON dosyalarının bulunduğu klasör yolunu girin (çıktı da aynı yerde oluşturulacak): ").strip()
    
    # Eğer boş bırakılırsa varsayılan yolu kullan
    if not base_path:
        base_path = r"c:\Users\Hp\Desktop\SDP\Wikipedia_Wikidata_compare"
        print(f"Varsayılan yol kullanılıyor: {base_path}")
    
    return base_path

def load_all_json_files(base_path):
    """
    Tüm JSON dosyalarını yükler ve birleştirir
    """
    files_to_process = [
        "LLMWithCasualDataExample.json",
        "LLMwithWikiDataExample.json", 
        "WikiDataTriples.json"
    ]
    
    print(f"\nJSON dosyaları aranıyor: {base_path}")
    
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
    print("=== Merge İşlemleri Başlatılıyor ===")
    
    # Kullanıcıdan yolu al (hem JSON okuma hem de çıktı için aynı yer)
    base_path = get_user_input()
    
    # Tüm JSON dosyalarını yükle
    all_data, total_original = load_all_json_files(base_path)
    
    if not all_data:
        print("Hiç veri yüklenemedi!")
        return
    
    print(f"\nToplam orijinal kayıt sayısı: {total_original}")
    
    # mergedformOfAboveTriples klasörünü aynı konumda oluştur
    output_dir = os.path.join(base_path, "mergedformOfAboveTriples")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Klasör oluşturuldu: {output_dir}")
    else:
        print(f"Mevcut klasör kullanılıyor: {output_dir}")
    
    # 1. Entity Types Merge
    print("\n1. Entity Types Merge işlemi...")
    entity_type_data = merge_entity_types(all_data)
    print(f"   Toplam unique varlık sayısı: {len(entity_type_data)}")
    
    # Entity Types sonucunu kaydet
    entity_types_file = os.path.join(output_dir, "entity_types_merged.json")
    with open(entity_types_file, 'w', encoding='utf-8') as f:
        json.dump(entity_type_data, f, ensure_ascii=False, indent=2)
    print(f"   Kaydedildi: {entity_types_file}")
    
    # 2. Relations Merge
    print("\n2. Relations Merge işlemi...")
    relations_data = merge_json_relations(all_data)
    print(f"   Birleştirilen relation kayıt sayısı: {len(relations_data)}")
    
    # Relations sonucunu kaydet
    relations_file = os.path.join(output_dir, "relations_merged.json")
    with open(relations_file, 'w', encoding='utf-8') as f:
        json.dump(relations_data, f, ensure_ascii=False, indent=2)
    print(f"   Kaydedildi: {relations_file}")
    
    # 3. Relations and Types Merge
    print("\n3. Relations and Types Merge işlemi...")
    relations_types_data = merge_json_with_types(all_data)
    print(f"   Birleştirilen relation+types kayıt sayısı: {len(relations_types_data)}")
    
    # Relations and Types sonucunu kaydet
    relations_types_file = os.path.join(output_dir, "relations_and_types_merged.json")
    with open(relations_types_file, 'w', encoding='utf-8') as f:
        json.dump(relations_types_data, f, ensure_ascii=False, indent=2)
    print(f"   Kaydedildi: {relations_types_file}")
    
    # İstatistikleri de ayrı bir dosyaya kaydet
    statistics = {
        "original_records": total_original,
        "unique_entities": len(entity_type_data),
        "merged_relations": len(relations_data),
        "merged_relations_with_types": len(relations_types_data),
        "reduction_stats": {
            "entity_types_reduction": f"{total_original} -> {len(entity_type_data)}",
            "relations_reduction": f"{total_original} -> {len(relations_data)}",
            "relations_types_reduction": f"{total_original} -> {len(relations_types_data)}"
        }
    }
    
    statistics_file = os.path.join(output_dir, "statistics.json")
    with open(statistics_file, 'w', encoding='utf-8') as f:
        json.dump(statistics, f, ensure_ascii=False, indent=2)
    print(f"   İstatistikler kaydedildi: {statistics_file}")
    
    print(f"\n=== TÜM MERGE İŞLEMLERİ TAMAMLANDI ===")
    print(f"Sonuçlar kaydedildi: {output_dir}")
    print(f"\nOluşturulan dosyalar:")
    print(f"1. entity_types_merged.json - {len(entity_type_data)} unique varlık")
    print(f"2. relations_merged.json - {len(relations_data)} birleştirilen relation")
    print(f"3. relations_and_types_merged.json - {len(relations_types_data)} birleştirilen relation+types")
    print(f"4. statistics.json - İstatistik bilgileri")
    
    # Kısa bir önizleme göster
    print(f"\n=== ÖNIZLEME ===")
    print("Entity Types (ilk 3):")
    for i, item in enumerate(entity_type_data[:3]):
        print(f"  {i+1}. {item}")
    
    print("\nRelations (ilk 3):")
    for i, item in enumerate(relations_data[:3]):
        print(f"  {i+1}. {item}")
    
    print("\nRelations with Types (ilk 3):")
    for i, item in enumerate(relations_types_data[:3]):
        print(f"  {i+1}. {item}")

if __name__ == "__main__":
    main()