import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin
import re

BASE_URL = "https://tr.wikipedia.org"


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


def vcard_verilerini_cek(soup):
    """Sayfadaki sağ bilgi kutusundaki (infobox) verileri çeker."""
    vcard = soup.select_one('.vcard')
    if not vcard:
        return {}

    vcard_dict = {}
    key_counter = {}  # Aynı key'lerin kaç kez geçtiğini takip et
    rows = vcard.select('tr')

    for row in rows:
        th = row.find('th')
        td = row.find('td')
        
        # Eğer hem th hem td yoksa veya sadece biri varsa farklı yaklaşım dene
        if not th and not td:
            continue
            
        # Sadece th varsa (tek sütunlu başlık olabilir)
        if th and not td:
            key = th.get_text(strip=True)
            if key:
                # Aynı key varsa numaralandır
                if key in key_counter:
                    key_counter[key] += 1
                    numbered_key = f"{key} ({key_counter[key]})"
                else:
                    key_counter[key] = 1
                    numbered_key = key
                
                if numbered_key not in vcard_dict:
                    vcard_dict[numbered_key] = ""
            continue
        
        # Sadece td varsa (önceki satırın devamı olabilir)
        if not th and td:
            # Son eklenen key'e ekle veya atla
            if vcard_dict:
                last_key = list(vcard_dict.keys())[-1]
                additional_value = []
                for item in td.contents:
                    if item.name is None:
                        text = str(item).strip()
                        if text:
                            additional_value.append(text)
                    elif item.name == 'a':
                        link_text = item.get_text().strip()
                        href = item.get('href')
                        if link_text and href:
                            full_url = urljoin(BASE_URL, href)
                            formatted_link = f"<PossibleEntity>{link_text}</PossibleEntity> <URL>:({full_url})</URL>"
                            additional_value.append(formatted_link)
                    else:
                        text = item.get_text().strip()
                        if text:
                            additional_value.append(text)
                
                if additional_value:
                    add_val = " ".join(additional_value).strip()
                    add_val = re.sub(r'\s+', ' ', add_val)
                    add_val = re.sub(r'\[\d+\]', '', add_val)
                    if vcard_dict[last_key]:
                        vcard_dict[last_key] += " " + add_val
                    else:
                        vcard_dict[last_key] = add_val
            continue

        # Normal durum: hem th hem td var
        key = th.get_text(strip=True)
        if not key:
            continue
            
        value_parts = []

        # td içindeki tüm içeriği recursive olarak tara
        def extract_content(element):
            """Özyinelemeli olarak tüm içeriği çıkar"""
            parts = []
            for item in element.contents:
                if item.name is None:
                    text = str(item).strip()
                    if text:
                        parts.append(text)
                elif item.name == 'a':
                    link_text = item.get_text().strip()
                    href = item.get('href')
                    if link_text and href:
                        full_url = urljoin(BASE_URL, href)
                        formatted_link = f"<PossibleEntity>{link_text}</PossibleEntity> <URL>:({full_url})</URL>"
                        parts.append(formatted_link)
                elif item.name == 'br':
                    parts.append(' ')
                elif item.name in ['ul', 'ol']:
                    # Liste elemanları için
                    for li in item.find_all('li'):
                        parts.extend(extract_content(li))
                        parts.append(' ')
                elif item.name == 'div' or item.name == 'span':
                    # Div ve span içindekiler için recursive
                    parts.extend(extract_content(item))
                else:
                    # Diğer etiketler için text al
                    text = item.get_text().strip()
                    if text:
                        parts.append(text)
            return parts

        value_parts = extract_content(td)
        
        value = " ".join(value_parts).strip()
        value = re.sub(r'\s+', ' ', value)
        value = re.sub(r'\[\d+\]', '', value)
        
        # Aynı key birden fazla kez gelmişse numaralandır
        if key in key_counter:
            key_counter[key] += 1
            final_key = f"{key} ({key_counter[key]})"
        else:
            key_counter[key] = 1
            final_key = key
        
        # Eğer bu numaralı key zaten varsa (nadiren olur) üzerine yaz
        vcard_dict[final_key] = value

    return vcard_dict


def cumlelere_ayir(metin):

    if not metin or not isinstance(metin, str):
        return []

    # --- 1️⃣ Entity bloklarını koruma ---
    placeholders = {}
    entity_pattern = r"<PossibleEntity>.*?</PossibleEntity> <URL>:\(.*?\)</URL>"

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
    """Wikipedia sayfasını tarar, Card ve Main yapısına uygun JSON döndürür."""
    soup = web_scraping_yap(url)
    if soup is None:
        return {"hata": "HTML içeriği alınamadı."}

    baslik = (
        soup.title.string.replace(" - Vikipedi", "").strip()
        if soup.title else "Başlık Bulunamadı"
    )

    card = vcard_verilerini_cek(soup)
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
                    full_url = urljoin(BASE_URL, href)
                    formatted_link = f"<PossibleEntity>{link_text}</PossibleEntity> <URL>:({full_url})</URL>"
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
