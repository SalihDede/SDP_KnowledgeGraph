import os, time, json
import pandas as pd
from urllib.parse import urljoin, quote, urlparse
import re
from scrapWikipedia import veri_cek_ve_json_olarak_dondur
from getEntityUrlFreq import analiz_yap

BASE_URL = "https://tr.wikipedia.org"

def wiki_url_from_name(name: str) -> str:
    return f"{BASE_URL}/wiki/{quote(name.replace(' ', '_'))}"

def safe_slug(text: str) -> str:
    return "_".join(text.strip().split())

def _combine_unique(dfs: list[pd.DataFrame]) -> pd.DataFrame | None:
    """
    Birden çok DataFrame'i URL'e göre TEKILLEŞTIRIR (her U için 1 satır).
    - E kolonu: aynı URL için en yüksek toplam Frekans'a sahip etiket seçilir.
    - Frekans: aynı URL için tüm kayıtların toplamı.
    - Kaynak_IDler: birleşik benzersiz ID seti.
    """
    if not dfs:
        return None
    df = pd.concat(dfs, ignore_index=True)
    if "U" not in df.columns:
        return df.drop_duplicates()

    freq_col = next((c for c in ["F", "Freq", "Frekans", "Frequency", "Count"] if c in df.columns), None)

    def choose_e_df(sub: pd.DataFrame) -> str:
        if "E" not in sub.columns or sub.empty:
            return ""
        if freq_col and freq_col in sub.columns:
            grp = sub.groupby("E")[freq_col].sum().sort_values(ascending=False)
            top_val = grp.iloc[0]
            candidates = grp[grp == top_val].index.tolist()
            return sorted(candidates)[0]
        return sorted(sub["E"].astype(str).tolist())[0]

    def merge_ids_df(sub: pd.DataFrame) -> str:
        if "Kaynak_IDler" not in sub.columns:
            return ""
        parts = ";".join(map(str, sub["Kaynak_IDler"].dropna())).split(";")
        uniq = sorted(set([p for p in parts if p]))
        return ";".join(uniq)

    rows = []
    for u, sub in df.groupby("U"):
        row = {
            "E": choose_e_df(sub),
            "U": str(u),
            "Kaynak_IDler": merge_ids_df(sub),
        }
        if freq_col and freq_col in sub.columns:
            row[freq_col] = int(sub[freq_col].sum())
        rows.append(row)

    out = pd.DataFrame(rows)
    cols = ["E", "U"] + ([freq_col] if freq_col and freq_col in out.columns else []) + (["Kaynak_IDler"] if "Kaynak_IDler" in out.columns else [])
    return out[cols]

def _combine_intersection_unique(dfs: list[pd.DataFrame]) -> pd.DataFrame | None:
    """
    Tüm DataFrame'lerin KESIŞIMINDE kalan URL'leri döndürür (her U için 1 satır).
    - E: tüm run'lardan gelen kayıtlar arasında toplam frekansı en yüksek etiket
    - Frekans: tüm run'lar toplamı
    - Kaynak_IDler: birleşik benzersiz set
    """
    if not dfs:
        return None
    # Canonical key: dilden bağımsızlaştır (en/tr)
    def canonical_key(u: str) -> str:
        return re.sub(r"^https?://(en|tr)\.wikipedia\.org/", "", str(u))

    # Hepsinde olma koşulu (canonical key üzerinden)
    sets = []
    for d in dfs:
        if "U" not in d.columns:
            return None
        sets.append({canonical_key(u) for u in d["U"].astype(str)})
    common_keys = set.intersection(*sets) if sets else set()
    if not common_keys:
        return pd.DataFrame(columns=["E", "U", "Frekans", "Kaynak_IDler"])  # boş kesişim

    all_df = pd.concat(dfs, ignore_index=True)
    all_df = all_df[all_df["U"].astype(str).apply(canonical_key).isin(common_keys)].copy()

    freq_col = next((c for c in ["F", "Freq", "Frekans", "Frequency", "Count"] if c in all_df.columns), None)

    def choose_e_df(sub: pd.DataFrame) -> str:
        if "E" not in sub.columns or sub.empty:
            return ""
        if freq_col and freq_col in sub.columns:
            grp = sub.groupby("E")[freq_col].sum().sort_values(ascending=False)
            top_val = grp.iloc[0]
            candidates = grp[grp == top_val].index.tolist()
            return sorted(candidates)[0]
        return sorted(sub["E"].astype(str).tolist())[0]

    def merge_ids_df(sub: pd.DataFrame) -> str:
        if "Kaynak_IDler" not in sub.columns:
            return ""
        parts = ";".join(map(str, sub["Kaynak_IDler"].dropna())).split(";")
        uniq = sorted(set([p for p in parts if p]))
        return ";".join(uniq)

        # Eski agg tarzını kullanmıyoruz; aşağıdaki manual gruplayıcı ile ilerliyoruz.

    # Grup canonical key ile; sonra tr > en önceliğiyle bir URL seç
    def pick_preferred_url(urls: list[str]) -> str:
        urls_sorted = sorted(map(str, set(urls)))
        for u in urls_sorted:
            if u.startswith("https://tr.wikipedia.org/"):
                return u
        for u in urls_sorted:
            if u.startswith("https://en.wikipedia.org/"):
                return u
        return urls_sorted[0]

    all_df["_canon"] = all_df["U"].astype(str).apply(canonical_key)
    grouped = []
    for canon, sub in all_df.groupby("_canon"):
        row = {
            "E": choose_e_df(sub),
            "U": pick_preferred_url(sub["U"].tolist()),
            "Kaynak_IDler": merge_ids_df(sub),
        }
        if freq_col and freq_col in sub.columns:
            row[freq_col] = int(sub[freq_col].sum())
        grouped.append(row)

    out = pd.DataFrame(grouped)
    cols = ["E", "U"] + ([freq_col] if freq_col and freq_col in out.columns else []) + (["Kaynak_IDler"] if "Kaynak_IDler" in out.columns else [])
    return out[cols]

def derin_scrap(root_url, max_depth=2, bekleme_suresi=1, etiket=None, output_dir=None):
    """
    root_url'den başlayarak max_depth derinlikte scrape + entity-URL analizi.
    Klasöre parça JSON/CSV yazar, sonunda kişi/URL bazlı E_U_Toplam_<etiket>.csv üretir.
    Dönen: (pd.DataFrame | None, str | None) -> (birleşik_df, birleşik_csv_yolu)
    """
    ziyaret_edilenler = set()
    kuyruk = [(root_url, 0)]
    tum_sonuclar = []
    sayac = 0

    if output_dir is None:
        output_dir = os.path.join("out", safe_slug(etiket or "run"))
    os.makedirs(output_dir, exist_ok=True)

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
        sayac += 1
        json_dosya = os.path.join(output_dir, f"Wiki_{derinlik}_{sayac}.json")
        with open(json_dosya, "w", encoding="utf-8") as f:
            json.dump(veri, f, indent=4, ensure_ascii=False)

        # Entity analizi (tek sayfa CSV)
        parcacsv = os.path.join(output_dir, f"E_U_{derinlik}_{sayac}.csv")
        df = analiz_yap(json_dosya, cikti_csv_adi=parcacsv)

        if df is not None and not df.empty:
            tum_sonuclar.append(df)

            # Yeni bağlantılar (sadece Wikipedia makale iç linkleri)
            yeni_linkler = set()
            for _, satir in df.iterrows():
                u = str(satir.get("U", ""))
                # Yalnızca en.wikipedia.org veya tr.wikipedia.org alanları ve /wiki/ ile başlayan makaleler
                if not (u.startswith("https://tr.wikipedia.org/wiki/") or u.startswith("https://en.wikipedia.org/wiki/")):
                    continue
                if any(x in u for x in ["action=", "redlink=1", "/w/index.php"]):
                    continue
                title = u.split("/wiki/", 1)[1]
                if ":" in title:  # Kategori:, Dosya:, Özel: vb.
                    continue
                yeni_linkler.add(u)

            for yeni_url in yeni_linkler:
                if yeni_url not in ziyaret_edilenler:
                    kuyruk.append((yeni_url, derinlik + 1))

            print(f"🌀 {len(yeni_linkler)} yeni bağlantı eklendi. Kuyruk boyutu: {len(kuyruk)}")
        else:
            print("⚠️ Hiç entity–URL çifti bulunamadı.")
        time.sleep(bekleme_suresi)

    # Kişi/URL bazlı birleşik CSV
    if tum_sonuclar:
        birlesik_df = _combine_unique(tum_sonuclar)
        if birlesik_df is None or birlesik_df.empty:
            birlesik_df = pd.concat(tum_sonuclar, ignore_index=True).drop_duplicates()
        etiket_slug = safe_slug(etiket or "run")
        birlesik_yol = os.path.join(output_dir, f"E_U_Toplam_{etiket_slug}.csv")
        birlesik_df.to_csv(birlesik_yol, index=False, encoding="utf-8-sig")
        print(f"\n✅ '{etiket_slug}' bitti. {birlesik_yol} oluşturuldu.")
        return birlesik_df, birlesik_yol
    else:
        print("⚠️ Hiç veri oluşturulamadı.")
        return None, None

if __name__ == "__main__":
    try:
        roots_input = input("Root Wikipedia URL(leri) (virgülle ayır): ").strip()
        depth = int(input("Maksimum derinlik (örn 2): ").strip())
    except Exception as e:
        print(f"Hatalı giriş: {e}")
        raise SystemExit(1)

    urls = [u.strip() for u in roots_input.split(",") if u.strip()]
    if not urls:
        print("En az bir URL girin.")
        raise SystemExit(1)

    hepsi = []
    for root in urls:
        if not root.startswith("http"):
            print(f"Atlandı (geçersiz URL): {root}")
            continue
        etiket = root.rsplit("/", 1)[-1]
        try:
            df, _ = derin_scrap(root, max_depth=depth, etiket=etiket)
            if df is not None and not df.empty:
                hepsi.append(df)
        except Exception as e:
            print(f"Hata ({root}): {e}")

    if hepsi:
        # Kesişim: tüm run'larda yer alan URL'ler
        all_df = _combine_intersection_unique(hepsi)
        all_dir = os.path.join("out", "ALL")
        os.makedirs(all_dir, exist_ok=True)
        all_csv = os.path.join(all_dir, "E_U_Toplam_ALL.csv")
        all_df.to_csv(all_csv, index=False, encoding="utf-8-sig")
        print(f"\n🌟 Tüm girdilerin KESİŞİMİ (her URL 1 satır): {all_csv}")
