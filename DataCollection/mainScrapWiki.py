import json
import time
import os
from urllib.parse import urljoin
from scrapWikipedia import veri_cek_ve_json_olarak_dondur
from getEntityUrlFreq import analiz_yap

BASE_URL = "https://tr.wikipedia.org"

def derin_scrap(root_url, max_depth=2, bekleme_suresi=1):
    """
    Belirtilen Wikipedia URL'sinden başlayarak max_depth derinliğe kadar
    recursive scraping ve entity frekans analizi yapar.
    """
    ziyaret_edilenler = set()
    kuyruk = [(root_url, 0)]
    tum_sonuclar = []

    while kuyruk:
        url, derinlik = kuyruk.pop(0)
        if url in ziyaret_edilenler or derinlik > max_depth:
            continue

        print(f"\n🌐 [{derinlik}] {url} sayfası işleniyor...")
        ziyaret_edilenler.add(url)

        veri = veri_cek_ve_json_olarak_dondur(url)
        if "hata" in veri:
            print(f"❌ Hata: {veri['hata']}")
            continue

        # JSON kaydet
        json_dosya = f"Wiki_{derinlik}_{len(ziyaret_edilenler)}.json"
        with open(json_dosya, "w", encoding="utf-8") as f:
            json.dump(veri, f, indent=4, ensure_ascii=False)

        # Entity analizi
        df = analiz_yap(json_dosya, cikti_csv_adi=f"E_U_{derinlik}_{len(ziyaret_edilenler)}.csv")
        if df is not None:
            tum_sonuclar.append(df)

        # Yeni bağlantılar çıkar (sadece Wikipedia bağlantıları)
        yeni_linkler = set()
        for _, satir in df.iterrows():
            if satir["U"].startswith(BASE_URL):
                yeni_linkler.add(satir["U"])

        # Kuyruğa ekle
        for yeni_url in yeni_linkler:
            if yeni_url not in ziyaret_edilenler:
                kuyruk.append((yeni_url, derinlik + 1))

        print(f"🌀 {len(yeni_linkler)} yeni bağlantı eklendi. Kuyruk boyutu: {len(kuyruk)}")
        time.sleep(bekleme_suresi)

    # Tüm CSV'leri birleştir
    if tum_sonuclar:
        import pandas as pd
        ana_df = pd.concat(tum_sonuclar, ignore_index=True)
        ana_df.to_csv("E_U_Toplam.csv", index=False, encoding="utf-8-sig")
        print("\n✅ Tüm sayfalar işlendi. 'E_U_Toplam.csv' oluşturuldu.")
    else:
        print("⚠️ Hiç veri oluşturulamadı.")


if __name__ == "__main__":
    root = input("🌍 Root Wikipedia URL'sini girin: ").strip()
    depth = int(input("🔢 Maksimum derinlik (örnek 2-3): ").strip())
    derin_scrap(root, max_depth=depth)
