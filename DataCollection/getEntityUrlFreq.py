import json
import re
import pandas as pd
from collections import defaultdict
import glob
import os

# 🌍 Global sözlükler — tüm dosyalar için ortak toplama alanı
# NOTE: Sadece URL bazında analiz yapmak için GLOBAL_U_TO_E ve GLOBAL_EU_TO_SENTENCES kritik.
# GLOBAL_FREKANS'ı (E,U) tabanlı olarak tutmaya devam ediyoruz ama U tabanlı çıktı üreteceğiz.
GLOBAL_FREKANS = defaultdict(int)
GLOBAL_U_TO_E = defaultdict(set)
GLOBAL_EU_TO_IDS = defaultdict(set)
# Entity-URL çiftleri için cümleler. Anahtar: (Entity_Text, URL)
GLOBAL_EU_TO_SENTENCES = defaultdict(list) 

def temiz_entity_text(entity_text):
    """Entity text'ini temizle - gereksiz karakterleri ve formatları kaldır"""
    if not entity_text:
        return ""
    
    clean_text = entity_text.strip()
    # PossibleEntity tag'lerini kaldırmayın - sadece whitespace ve özel karakterleri temizleyin
    clean_text = re.sub(r'\s+', ' ', clean_text)
    clean_text = re.sub(r'^[=\-\s]+|[=\-\s]+$', '', clean_text)
    
    # Eğer = işareti varsa sol tarafı al (genellikle daha clean)
    if '=' in clean_text and not clean_text.startswith('='):
        parts = [p.strip() for p in clean_text.split('=')]
        clean_text = parts[0] if parts[0] else clean_text
    
    return clean_text.strip()

def analiz_yap(json_dosya_yolu, cikti_csv_adi="E_U_Ciftleri_Frekansli.csv"):
    """
    Tek JSON için entity–URL frekans analizi.
    Ayrıca global toplama (GLOBAL_U_TO_E, GLOBAL_EU_TO_SENTENCES) verisine ekleme yapar.
    """
    pattern = r"<PossibleEntity>(.*?)</PossibleEntity> <URL>:(.*?)</URL>"

    frekans_dict = defaultdict(int)
    u_to_e = defaultdict(set)
    e_u_to_ids = defaultdict(set)
    local_seen_pairs = set() 

    with open(json_dosya_yolu, "r", encoding="utf-8") as f:
        data = json.load(f)

    def metinleri_tara(text, current_id=None, full_sentence=None):
        for match in re.finditer(pattern, text):
            e_text = match.group(1).strip()
            u_link = match.group(2).strip()
            
            e_text_clean = temiz_entity_text(e_text)
            
            if e_text_clean and u_link:
                # Yerel ve Global Entity-URL takibi (GLOBAL_FREKANS)
                frekans_dict[(e_text_clean, u_link)] += 1
                local_seen_pairs.add((e_text_clean, u_link))
                u_to_e[u_link].add(e_text_clean)
                if current_id:
                    e_u_to_ids[(e_text_clean, u_link)].add(current_id)
                
                # Global Cümle kaydı - Anahtar: (Entity, URL)
                if full_sentence:
                    # Cümleyi sadece bir kere kaydetmek için unique kontrolü 
                    # (aynı (E,U) çifti aynı cümlede 2 kez geçebilir)
                    sentence_key = (current_id, full_sentence)
                    
                    current_sentences = GLOBAL_EU_TO_SENTENCES.get((e_text_clean, u_link), [])
                    
                    # Eğer bu (ID, Cümle) çifti listede yoksa ekle
                    if not any(item['id'] == current_id and item['sentence'] == full_sentence for item in current_sentences):
                        GLOBAL_EU_TO_SENTENCES[(e_text_clean, u_link)].append({
                            'id': current_id,
                            'sentence': full_sentence
                        })
                

    # 1️⃣ Main kısmı tara
    for item in data.get("Main", []):
        cumle = item.get("sentence", "")
        current_id = item.get("id")
        metinleri_tara(cumle, current_id, full_sentence=cumle)

    # 2️⃣ Card kısmı tara
    card = data.get("Card", {})
    title = data.get("Title", "Bilinmeyen")
    for i, (key, val) in enumerate(card.items(), start=1):
        if isinstance(val, str):
            current_id = f"{title}Card#{i}"
            # Card'dan gelen metni de cümle olarak kabul ediyoruz
            metinleri_tara(val, current_id=current_id, full_sentence=val)

    # ✅ 3️⃣ Global'e sadece unique çiftleri ekle 
    for (e_text, u_link) in local_seen_pairs:
        GLOBAL_FREKANS[(e_text, u_link)] = 1
        # Bu satır en kritik satırdır, aynı URL'ye işaret eden tüm Entity'leri toplar.
        GLOBAL_U_TO_E[u_link].add(e_text) 
        GLOBAL_EU_TO_IDS[(e_text, u_link)].update(e_u_to_ids.get((e_text, u_link), set()))

    # 4️⃣ Bu dosya için CSV üret (Orijinal hali korunuyor)
    if not frekans_dict:
        print(f"⚠️ {json_dosya_yolu}: Hiç entity–URL çifti bulunamadı.")
        return pd.DataFrame(columns=["E", "U", "Frekans", "Kaynak_IDler"])

    final_kayitlar = []
    for (e_text, u_link), freq in frekans_dict.items():
        # Bu yerel çıktı için Entity birleştirmesi kaldırıldı (Orijinal yapısı korundu)
        id_list = sorted(list(e_u_to_ids.get((e_text, u_link), [])))
        # 🔹 ID + Cümle bilgilerini de ekle
    for (e_text, u_link), freq in frekans_dict.items():
        idler = sorted(list(e_u_to_ids.get((e_text, u_link), [])))
        detay_listesi = []

        # Her (E,U) için global cümle kaydını bul
        for sent_info in GLOBAL_EU_TO_SENTENCES.get((e_text, u_link), []):
            current_id = sent_info.get("id", "")
            cumle = sent_info.get("sentence", "")
            # PossibleEntity tag'lerini entity adıyla değiştir
            clean_cumle = re.sub(r'<PossibleEntity>(.*?)</PossibleEntity> <URL>:(.*?)</URL>', r'\1', cumle)
            clean_cumle = re.sub(r'\s+', ' ', clean_cumle).strip()

            if current_id and clean_cumle:
                detay_listesi.append(f"{current_id}: {clean_cumle}")

        # Eğer detaylar boşsa sadece ID'leri yaz
        id_birlestirilmis = " | ".join(detay_listesi) if detay_listesi else " | ".join(idler)

        final_kayitlar.append({
            "E": e_text,
            "U": u_link,
            "Frekans": freq,
            "Kaynak_IDler": id_birlestirilmis
        })

    df = pd.DataFrame(final_kayitlar)
    df.sort_values(by="Frekans", ascending=False, inplace=True)
    df.to_csv(cikti_csv_adi, index=False, encoding="utf-8-sig")
    print(f"✅ {json_dosya_yolu}: {len(df)} unique (E,U) çifti bulundu ve '{cikti_csv_adi}' kaydedildi.")
    return df

def e_u_total_cikti(cikti_csv_adi="E_U_total_URL_Bazli.csv"):
    """
    💥 REVİZE SÜRÜM:
    Her URL (U) için tek satır oluşturur.
    Aynı URL'ye işaret eden tüm Entity'leri birleştirir ve cümleleri sadeleştirilmiş biçimde (sadece entity adı kalır) yazar.
    """
    import pandas as pd
    import re

    if not GLOBAL_U_TO_E:
        print("⚠️ Henüz global URL-Entity verisi yok.")
        return None

    final_kayitlar = []

    for u_link, e_set in GLOBAL_U_TO_E.items():
        # 1️⃣ Aynı URL'ye işaret eden Entity'leri birleştir
        e_list = sorted(list(e_set))
        e_text_birlestirilmis = " | ".join(e_list)

        # 2️⃣ Bu URL’ye ait tüm (E,U) cümlelerini topla
        tum_cumleler = []
        id_seen = set()

        for e_text in e_set:
            pair_key = (e_text, u_link)
            sentence_data = GLOBAL_EU_TO_SENTENCES.get(pair_key, [])

            for sent_info in sentence_data:
                sid = sent_info.get("id", "")
                sentence_raw = sent_info.get("sentence", "").strip()
                if not sentence_raw:
                    continue

                # Aynı cümle bir kez yazılsın
                if (sid, sentence_raw) in id_seen:
                    continue
                id_seen.add((sid, sentence_raw))

                # --- 🔹 ENTITY bloklarını sadeleştir: sadece E adını bırak ---
                def entity_replacer(match):
                    return match.group(1).strip()  # sadece entity adı

                sentence_clean = re.sub(
                    r"<PossibleEntity>(.*?)</PossibleEntity> <URL>:(.*?)</URL>", entity_replacer, sentence_raw
                )
                sentence_clean = re.sub(r'\s+', ' ', sentence_clean).strip()

                tum_cumleler.append(f"{sid}: {sentence_clean}")

        # 3️⃣ Tüm cümleleri tek satırda birleştir
        cumle_str = " | ".join(tum_cumleler)

        # 4️⃣ Son satır oluştur
        final_kayitlar.append({
            "E": e_text_birlestirilmis,
            "U": u_link,
            "Frekans": len(tum_cumleler),
            "Kaynak_IDler": cumle_str
        })

    df = pd.DataFrame(final_kayitlar)
    df.sort_values(by="Frekans", ascending=False, inplace=True)
    df.to_csv(cikti_csv_adi, index=False, encoding="utf-8-sig")

    print(f"\n🌍 {len(df)} unique URL için sadeleştirilmiş çıktı '{cikti_csv_adi}' oluşturuldu.")
    print("✅ Cümlelerde artık sadece entity isimleri görünüyor (___E...U(...)___ blokları kaldırıldı).")
    return df
