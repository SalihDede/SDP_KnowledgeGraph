#!/usr/bin/env python3
"""
İl-İlçe JSON'unu Triple formatına dönüştür
"""
import json
from pathlib import Path

INPUT_FILE  = r"C:\Users\Hp\Desktop\SDP\NewScrappingEras\Türkiye il-ilçe\il-ilce.json"
OUTPUT_FILE = r"C:\Users\Hp\Desktop\SDP\NewScrappingEras\Türkiye il-ilçe\il-ilce-triples.json"

KAYNAK_LLM_MODELI = "Gerekli değildir"
KAYNAK_SOURCE     = "github.com/furkan-dogu"
KAYNAK_URL        = "github.com/furkan-dogu/Turkiye-Sehir-ve-Ilceleri"
METIN             = "Veri şematik yapıdadır"


def make_entry(bas: str, bas_tipi: str, iliski: str, uc: str, uc_tipi: str) -> dict:
    return {
        "Kaynak_LLM_Modeli": KAYNAK_LLM_MODELI,
        "kaynak_source":     KAYNAK_SOURCE,
        "kaynak_url":        KAYNAK_URL,
        "metin":             METIN,
        "triple": {
            "baş":      bas,
            "baş_tipi": bas_tipi,
            "ilişki":   iliski,
            "uç":       uc,
            "uç_tipi":  uc_tipi
        }
    }


def convert(input_file: str, output_file: str):
    print(f"📖  Okunuyor: {input_file}\n")

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"🗂️   {len(data)} il bulundu\n")

    entries = []

    for il in data:
        il_adi     = il.get('il_adi', '')
        plaka_kodu = il.get('plaka_kodu', '')
        ilceler    = il.get('ilceler', [])

        # Triple 1 — İl'in plaka kodu
        entries.append(make_entry(
            bas=il_adi,      bas_tipi="İl",
            iliski="Plakası",
            uc=plaka_kodu,   uc_tipi="Kod"
        ))

        for ilce in ilceler:
            ilce_adi  = ilce.get('ilce_adi', '')
            ilce_kodu = ilce.get('ilce_kodu', '')

            # Triple 2 — İlin ilçeleri
            entries.append(make_entry(
                bas=il_adi,    bas_tipi="İl",
                iliski="İlçeleri",
                uc=ilce_adi,   uc_tipi="İlçe"
            ))

            # Triple 3 — İlçe hangi ile bağlı
            entries.append(make_entry(
                bas=ilce_adi,  bas_tipi="İlçe",
                iliski="İlçesidir",
                uc=il_adi,     uc_tipi="İl"
            ))

            # Triple 4 — İlçenin kodu
            entries.append(make_entry(
                bas=ilce_adi,  bas_tipi="İlçe",
                iliski="Kodu",
                uc=ilce_kodu,  uc_tipi="Kod"
            ))

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"✅  Tamamlandı!")
    print(f"   Toplam kayıt : {len(entries)}")
    print(f"   Çıktı        : {output_file}")

    print(f"\n📋  İlk 3 kayıt örneği:\n")
    for entry in entries[:3]:
        t = entry['triple']
        print(f"   {t['baş']} → {t['ilişki']} → {t['uç']}")


if __name__ == "__main__":
    inp = Path(INPUT_FILE)
    if not inp.exists():
        print(f"❌  Girdi dosyası bulunamadı:\n   {INPUT_FILE}")
    else:
        convert(INPUT_FILE, OUTPUT_FILE)