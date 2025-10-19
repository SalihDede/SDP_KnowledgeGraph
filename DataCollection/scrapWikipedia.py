import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin, urlparse
import re

BASE_URL = "https://tr.wikipedia.org"  # varsayılan, fakat sayfa bazlı base kullanılacak


def web_scraping_yap(url):
    """Wikipedia sayfasını indirir ve BeautifulSoup nesnesi döner."""
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return None
    return BeautifulSoup(response.content, 'html.parser')


def vcard_verilerini_cek(soup, page_base_url: str):
    """Sayfadaki sağ bilgi kutusundaki (infobox) verileri çeker.
    Linkleri, sayfanın kendi alan adına göre (en/tr) birleştirir.
    """
    vcard = soup.select_one('.vcard')
    if not vcard:
        return {}

    vcard_dict = {}
    rows = vcard.select('tr')

    for row in rows:
        th = row.find('th')
        td = row.find('td')
        if not th or not td:
            continue

        key = th.get_text(strip=True)
        value_parts = []

        for item in td.contents:
            if item.name is None:
                text = str(item).strip()
                if text:
                    value_parts.append(text)
            elif item.name == 'a':
                link_text = item.get_text().strip()
                href = item.get('href')
                if link_text and href:
                    # href mutlaksa aynen kullan, değilse sayfa domaini ile birleştir
                    full_url = urljoin(page_base_url, href)
                    formatted_link = f"___E:{link_text} U:({full_url})___"
                    value_parts.append(formatted_link)
            else:
                text = item.get_text().strip()
                if text:
                    value_parts.append(text)

        value = " ".join(value_parts).strip()
        value = re.sub(r'\s+', ' ', value)
        value = re.sub(r'\[\d+\]', '', value)
        vcard_dict[key] = value

    return vcard_dict


def cumlelere_ayir(metin):
    """
    Cümleleri ayırırken:
      - ___E:... U:(...)___ bloklarını korur
      - Kısaltmalarda (ör. 'd.', 'Dr.', 'Prof.') bölünmez
      - Sayılarda ('19.', '3.1', '2. Dünya') bölünmez
      - Noktanın cümle sonu olup olmadığını dinamik olarak analiz eder
    """
    if not metin or not isinstance(metin, str):
        return []

    # --- 1️⃣ Entity bloklarını koruma ---
    placeholders = {}
    entity_pattern = r"___E:.*?U:\(.*?\)___"

    def placeholderify(match):
        key = f"[[ENTITY_BLOCK_{len(placeholders)}]]"
        placeholders[key] = match.group(0)
        return key

    temp_text = re.sub(entity_pattern, placeholderify, metin)

    # --- 2️⃣ Sayılar veya kısaltmalardaki noktaları geçici koru ---
    temp_text = re.sub(r'(\d+)\.(\s*[a-zA-ZçğıöşüÇĞİÖŞÜ])', r'\1[[DOT]]\2', temp_text)
    temp_text = re.sub(r'\b([A-Za-zÇĞİÖŞÜçğıöşü]{1,4})\.(\s*[a-zA-ZçğıöşüÇĞİÖŞÜ])', r'\1[[DOT]]\2', temp_text)

    # --- 3️⃣ Cümleleri ayır (yalnızca gerçek sonlandırıcılar) ---
    raw_sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ])', temp_text.strip())

    # --- 4️⃣ Yer tutucuları geri koy ---
    final_sentences = []
    for s in raw_sentences:
        s = s.replace("[[DOT]]", ".")
        for key, original in placeholders.items():
            s = s.replace(key, original)
        s = s.strip()
        if s:
            final_sentences.append(s)

    return final_sentences


def veri_cek_ve_json_olarak_dondur(url):
    """Wikipedia sayfasını tarar, Card ve Main yapısına uygun JSON döndürür.
    Linkler sayfanın domainine göre (en/tr) oluşturulur.
    """
    soup = web_scraping_yap(url)
    if soup is None:
        return {"hata": "HTML içeriği alınamadı."}

    baslik = (
        soup.title.string.replace(" - Vikipedi", "").strip()
        if soup.title else "Başlık Bulunamadı"
    )

    parsed = urlparse(url)
    page_base_url = f"{parsed.scheme}://{parsed.netloc}"

    card = vcard_verilerini_cek(soup, page_base_url)
    paragraflar = soup.select('#mw-content-text p')

    main_yapisi = []

    for p in paragraflar:
        modified_text_parts = []
        for item in p.contents:
            if item.name is None:
                text = str(item).strip()
                if text:
                    modified_text_parts.append(text)
            elif item.name == 'a':
                link_text = item.get_text().strip()
                href = item.get('href')
                if link_text and href:
                    full_url = urljoin(page_base_url, href)
                    formatted_link = f"___E:{link_text} U:({full_url})___"
                    modified_text_parts.append(formatted_link)
            else:
                text = item.get_text().strip()
                if text:
                    modified_text_parts.append(text)

        full_text = " ".join(modified_text_parts).strip()
        if not full_text:
            continue

        full_text = re.sub(r'\s+', ' ', full_text)
        full_text = re.sub(r'\[\d+\]', '', full_text)

        cumleler = cumlelere_ayir(full_text)
        for i, cumle in enumerate(cumleler):
            main_yapisi.append({
                "id": f"{baslik}#{len(main_yapisi)+1}",
                "sentence": cumle
            })

    # Nihai JSON yapısı (başlık dahil)
    veri = {
        "Title": baslik,
        "Card": card,
        "Main": main_yapisi
    }

    return veri


# Test veya dış çağrılar için örnek kullanım
if __name__ == "__main__":
    test_url = "https://tr.wikipedia.org/wiki/Recep_Tayyip_Erdo%C4%9Fan"
    sonuc = veri_cek_ve_json_olarak_dondur(test_url)
    with open("WikiOutput.json", "w", encoding="utf-8") as f:
        json.dump(sonuc, f, indent=4, ensure_ascii=False)
    print("✅ WikiOutput.json dosyası oluşturuldu.")
