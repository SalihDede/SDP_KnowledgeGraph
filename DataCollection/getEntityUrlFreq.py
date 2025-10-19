import json
import re
import pandas as pd
from collections import defaultdict

def analiz_yap(json_dosya_yolu, cikti_csv_adi="E_U_Ciftleri_Frekansli.csv"):
    """
    Yeni JSON yapısına (Card + Main) uygun entity–URL frekans analiz aracı.
    Artık her entity–URL çiftinin hangi cümle ID'lerinde geçtiği de kaydedilir.
    """
    pattern = r"___E:(.*?) U:\((https?://[^\)]+)\)___"

    frekans_dict = defaultdict(int)
    u_to_e = defaultdict(set)
    e_u_to_ids = defaultdict(set)  # (entity, url) → id'ler

    with open(json_dosya_yolu, "r", encoding="utf-8") as f:
        data = json.load(f)

    def metinleri_tara(text, current_id=None):
        """Cümledeki entity–URL çiftlerini bulur ve frekans/ID ekler."""
        for match in re.finditer(pattern, text):
            e_text = match.group(1).strip()
            u_link = match.group(2).strip()
            frekans_dict[(e_text, u_link)] += 1
            u_to_e[u_link].add(e_text)
            if current_id:
                e_u_to_ids[(e_text, u_link)].add(current_id)

    # 1️⃣ Main içindeki cümleleri tara
    for item in data.get("Main", []):
        cumle = item.get("sentence", "")
        current_id = item.get("id")
        metinleri_tara(cumle, current_id)

    # 2️⃣ Card (vcard) içindeki metinleri de tara — Title bazlı ID oluştur
    card = data.get("Card", {})
    title = data.get("Title", "Bilinmeyen")  # JSON'daki sayfa başlığı alınır

    for i, (key, val) in enumerate(card.items(), start=1):
        if isinstance(val, str):
            current_id = f"{title}Card#{i}"   # örnek: "Kerem BürsinCard#1"
            metinleri_tara(val, current_id=current_id)

    # 3️⃣ Frekans kayıtlarını oluştur
    final_kayitlar = []
    for (e_text, u_link), freq in frekans_dict.items():
        e_list = sorted(list(u_to_e[u_link]))
        e_text_birlestirilmis = "=".join(e_list) if len(e_list) > 1 else e_text
        id_list = sorted(list(e_u_to_ids.get((e_text, u_link), [])))
        id_birlestirilmis = "=".join(id_list) if id_list else ""

        final_kayitlar.append({
            "E": e_text_birlestirilmis,
            "U": u_link,
            "Frekans": freq,
            "Kaynak_IDler": id_birlestirilmis,
            ## "TamMetin": f"E:{e_text_birlestirilmis} U:{u_link}"
        })

    # 4️⃣ DataFrame ve CSV çıktısı
    if not final_kayitlar:
        print("⚠️ Hiç entity–URL çifti bulunamadı.")
        return None

    df = pd.DataFrame(final_kayitlar)
    df.sort_values(by="Frekans", ascending=False, inplace=True)
    df.to_csv(cikti_csv_adi, index=False, encoding="utf-8-sig")

    print(f"✅ Toplam {len(df)} unique kayıt bulundu ve '{cikti_csv_adi}' dosyasına kaydedildi.\n")
    print("🔹 İlk 5 kayıt:")
    print(df.head())
    return df
