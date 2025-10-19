import json
import re
import pandas as pd
from collections import defaultdict, Counter

def analiz_yap(json_dosya_yolu, cikti_csv_adi="E_U_Ciftleri_Frekansli.csv"):
    """
    Card + Main metinlerinden ___E:<entity> U:(<url>)___ kalıplarını çıkarır.
    ÇIKTI GARANTİSİ: Her bir URL (U) için TEK satır üretir.
    - E: o URL için en sık görülen entity etiketi
    - Frekans: o URL'nin tüm entity varyantları dahil toplam görülme sayısı
    - Kaynak_IDler: o URL'nin geçtiği tüm cümle/alan ID'lerinin birleşimi
    """
    pattern = r"___E:(.*?) U:\((https?://[^\)]+)\)___"

    # (E,U) frekansları, U -> {E: freq}, U -> toplam freq, (E,U) -> id'ler
    e_u_freq = defaultdict(int)
    url_to_e_freq = defaultdict(lambda: defaultdict(int))
    url_total_freq = defaultdict(int)
    e_u_to_ids = defaultdict(set)

    with open(json_dosya_yolu, "r", encoding="utf-8") as f:
        data = json.load(f)

    def _allowed_wiki_article(u: str) -> bool:
        try:
            if "/wiki/" not in u:
                return False
            if any(x in u for x in ["action=", "redlink=1", "/w/index.php"]):
                return False
            title = u.split("/wiki/", 1)[1]
            # Kategori:, Dosya:, Özel:, Yardım: gibi ad alanlarını dışla
            if ":" in title:
                return False
            return True
        except Exception:
            return False

    def metinleri_tara(text, current_id=None):
        for match in re.finditer(pattern, text):
            e_text = match.group(1).strip()
            u_link = match.group(2).strip()
            if not _allowed_wiki_article(u_link):
                continue
            e_u_freq[(e_text, u_link)] += 1
            url_to_e_freq[u_link][e_text] += 1
            url_total_freq[u_link] += 1
            if current_id:
                e_u_to_ids[(e_text, u_link)].add(current_id)

    # 1️⃣ Main cümleleri
    for item in data.get("Main", []):
        cumle = item.get("sentence", "")
        current_id = item.get("id")
        metinleri_tara(cumle, current_id)

    # 2️⃣ Card alanları — Title bazlı ID
    card = data.get("Card", {})
    title = data.get("Title", "Bilinmeyen")
    for i, (key, val) in enumerate(card.items(), start=1):
        if isinstance(val, str):
            current_id = f"{title}Card#{i}"
            metinleri_tara(val, current_id=current_id)

    if not url_total_freq:
        print("⚠️ Hiç entity–URL çifti bulunamadı.")
        return None

    # 3️⃣ Dil-normalizasyonu: en/tr aynı makale başlığına işaret ediyorsa tek anahtar altında birleştir
    def canonical_key(u: str) -> str:
        # en.wikipedia.org/wiki/Foo → wiki/Foo ; tr.wikipedia.org/wiki/Foo → wiki/Foo
        try:
            return re.sub(r"^https?://(en|tr)\.wikipedia\.org/", "", u)
        except Exception:
            return u

    # tercih edilen alan adı sırası (tr > en)
    def pick_preferred_url(urls: list[str]) -> str:
        urls_sorted = sorted(urls)
        for u in urls_sorted:
            if u.startswith("https://tr.wikipedia.org/"):
                return u
        for u in urls_sorted:
            if u.startswith("https://en.wikipedia.org/"):
                return u
        return urls_sorted[0]

    # Canonical gruplayıp tekilleştir
    grouped_by_canon = defaultdict(list)
    for u_link in url_total_freq.keys():
        grouped_by_canon[canonical_key(u_link)].append(u_link)

    final_kayitlar = []
    for canon, urls in grouped_by_canon.items():
        # Bu canonical gruptaki tüm URL'lerin frekans ve id'lerini birleştir
        total_f = 0
        e_counter = defaultdict(int)
        all_ids = set()
        for u in urls:
            total_f += url_total_freq[u]
            for e_text, f in url_to_e_freq[u].items():
                e_counter[e_text] += f
            for e_text in url_to_e_freq[u].keys():
                all_ids.update(e_u_to_ids.get((e_text, u), set()))

        # En sık görülen entity etiketi
        best_e = sorted(e_counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        preferred_u = pick_preferred_url(urls)

        final_kayitlar.append({
            "E": best_e,
            "U": preferred_u,
            "Frekans": int(total_f),
            "Kaynak_IDler": ";".join(sorted(all_ids)) if all_ids else "",
        })

    df = pd.DataFrame(final_kayitlar)
    df.sort_values(by="Frekans", ascending=False, inplace=True)
    df.to_csv(cikti_csv_adi, index=False, encoding="utf-8-sig")

    print(f"✅ Toplam {len(df)} unique URL kaydı bulundu ve '{cikti_csv_adi}' dosyasına kaydedildi.\n")
    print("🔹 İlk 5 kayıt:")
    print(df.head())
    return df
