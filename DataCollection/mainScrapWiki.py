import json
import time
import os
from urllib.parse import urljoin
from scrapWikipedia import veri_cek_ve_json_olarak_dondur
from getEntityUrlFreq import analiz_yap, e_u_total_cikti
from entityFrequencyAnalyzer import EntityFrequencyAnalyzer

BASE_URL = "https://tr.wikipedia.org"

print("="*80)
print("🚀 Wikipedia Entity Frekans Analiz Sistemi")
print("="*80)
print("\n📋 İşlem Adımları:")
print("1️⃣  Wikipedia sayfasını al (tüm içerik)")
print("2️⃣  Sayfadaki linkleri bul")
print("3️⃣  Verileri URL bazlı çek ve entityleri al")
print("4️⃣  Farklı adda aynı URL varsa entity'ye ekle")
print("5️⃣  Unique linkleri queue'ya al ve aynı işlemi tekrarla")
print("6️⃣  Tüm frekans tablolarındaki entityleri birleştir")
print("7️⃣  Frekansları topla ve karşılık gelen cümleleri yaz")
print("="*80 + "\n")

def derin_scrap(root_url, max_depth=2, bekleme_suresi=1):
    """
    Wikipedia'dan derin scraping ve entity frekans analizi yapar.
    
    İşlem Akışı:
    1. Root URL'den başla
    2. Her sayfayı scrap et (tüm içeriği al)
    3. Sayfadaki entity-URL çiftlerini çıkar
    4. Sayfadaki Wikipedia linklerini bul
    5. Unique linkleri kuyruğa ekle
    6. Derinlik limiti dolana kadar devam et
    7. Tüm entity'leri URL bazlı birleştir ve frekansları topla
    """
    ziyaret_edilenler = set()
    kuyruk = [(root_url, 0)]
    tum_sonuclar = []
    json_dosyalar = []
    entity_analyzer = EntityFrequencyAnalyzer()

    print(f"\n🎯 Root URL: {root_url}")
    print(f"🔢 Maksimum Derinlik: {max_depth}")
    print(f"⏱️  Bekleme Süresi: {bekleme_suresi} saniye")
    print("="*80 + "\n")

    while kuyruk:
        url, derinlik = kuyruk.pop(0)
        if url in ziyaret_edilenler or derinlik > max_depth:
            continue

        print(f"\n{'  ' * derinlik}🌐 [Derinlik {derinlik}] Sayfa #{len(ziyaret_edilenler)+1}")
        print(f"{'  ' * derinlik}📍 URL: {url[:80]}...")
        ziyaret_edilenler.add(url)

        # 1️⃣ Sayfayı scrap et (TÜM sayfayı al)
        veri = veri_cek_ve_json_olarak_dondur(url)
        if "hata" in veri:
            print(f"{'  ' * derinlik}❌ Hata: {veri['hata']}")
            continue

        # 2️⃣ JSON kaydet
        json_dosya = f"Wiki_{derinlik}_{len(ziyaret_edilenler)}.json"
        with open(json_dosya, "w", encoding="utf-8") as f:
            json.dump(veri, f, indent=4, ensure_ascii=False)
        
        json_dosyalar.append(json_dosya)
        print(f"{'  ' * derinlik}✅ JSON kaydedildi: {json_dosya}")

        # 3️⃣ Entity analizi (URL bazlı - farklı adlarda aynı URL'yi birleştirir)
        df = analiz_yap(json_dosya, cikti_csv_adi=f"E_U_{derinlik}_{len(ziyaret_edilenler)}.csv")
        if df is not None:
            tum_sonuclar.append(df)
            print(f"{'  ' * derinlik}📊 {len(df)} farklı Entity-URL çifti bulundu")
        
        # 4️⃣ Kümülatif entity analizi
        entity_result = entity_analyzer.analyze_json_file(json_dosya)
        if "error" not in entity_result:
            print(f"{'  ' * derinlik}📈 {entity_result['unique_entities']} farklı entity, "
                      f"{entity_result['unique_pairs']} farklı entity-URL çifti")

        # 5️⃣ Yeni Wikipedia bağlantılarını bul
        yeni_linkler = set()
        for _, satir in df.iterrows():
            if satir["U"].startswith(BASE_URL):
                yeni_linkler.add(satir["U"])

        # 6️⃣ Unique linkleri kuyruğa ekle
        for yeni_url in yeni_linkler:
            if yeni_url not in ziyaret_edilenler:
                kuyruk.append((yeni_url, derinlik + 1))

        print(f"{'  ' * derinlik}🔗 {len(yeni_linkler)} yeni link bulundu, Kuyruk: {len(kuyruk)}")
        time.sleep(bekleme_suresi)

    # Tüm CSV'leri birleştir (Entity analizi)
    if tum_sonuclar:
        import pandas as pd
        ana_df = pd.concat(tum_sonuclar, ignore_index=True)
        ana_df.to_csv("E_U_Toplam.csv", index=False, encoding="utf-8-sig")
        print(f"\n✅ Entity analizi tamamlandı: {len(ana_df)} kayıt 'E_U_Toplam.csv' dosyasında.")
        
        # Global Entity raporu oluştur (URL BAZLI RAPOR)
        # ÇIKTI DOSYA ADI DEĞİŞTİRİLDİ
        e_u_total_cikti("E_U_URL_Bazli_Global_Toplam_Cümleler_Dahil.csv")
    
    # Kümülatif Entity frekans analizi tamamla
    if json_dosyalar:
        print(f"\n📊 {len(json_dosyalar)} sayfa için KÜMÜLATIF entity frekans analizi yapılıyor...")
        
        # Kümülatif entity raporları oluştur
        entity_df, pair_df = entity_analyzer.save_reports(
            entity_report_file="KUMÜLATIF_Entity_Frekanslari.csv",
            pair_report_file="KUMÜLATIF_Entity_URL_Ciftleri.csv",
            min_frequency=2
        )
        
        if entity_df is not None and not entity_df.empty:
            print(f"\n🔥 EN SIK GEÇEN 20 ENTİTY (Kümülatif):")
            top_entities = entity_analyzer.get_top_entities(20)
            print(top_entities[["Entity", "Sayfa_Frekans", "Kaynak_Sayfa_Sayisi"]].to_string(index=False))
            
            # Özet bilgi
            total_unique_entities = len(entity_analyzer.global_entity_freq)
            total_unique_pairs = len(entity_analyzer.entity_url_pairs)
            print(f"\n📈 KÜMÜLATIF İSTATİSTİKLER:")
            print(f"   • Toplam farklı entity: {total_unique_entities}")
            print(f"   • Toplam farklı entity-URL çifti: {total_unique_pairs}")
            print(f"   • Analiz edilen sayfa: {len(json_dosyalar)}")
            print(f"   • Minimum 2 sayfada geçen entity: {len(entity_df)}")
        
        print("\n✅ TÜM ANALİZLER TAMAMLANDI!")
        print("📁 Oluşturulan dosyalar:")
        print("   • E_U_Toplam.csv (Eski sistem - Tek tek E,U çiftleri)")
        # ÇIKTI MESAJI İSTEĞİNİZE GÖRE GÜNCELLENDİ
        print("   • E_U_URL_Bazli_Global_Toplam_Cümleler_Dahil.csv (TÜM Sayfalarda URL bazlı Entity birleştirme ve Cümle listesi)")
        print("   • KUMÜLATIF_Entity_Frekanslari.csv (YENİ - Entity frekansları, Sayfa bazlı sayım)")
        print("   • KUMÜLATIF_Entity_URL_Ciftleri.csv (YENİ - Entity-URL çift frekansları, Sayfa bazlı sayım)")
        
    else:
        print("⚠️ Hiç veri oluşturulamadı.")


if __name__ == "__main__":
    root = input("🌍 Root Wikipedia URL'sini girin: ").strip()
    depth = int(input("🔢 Maksimum derinlik (örnek 2-3): ").strip())
    derin_scrap(root, max_depth=depth)