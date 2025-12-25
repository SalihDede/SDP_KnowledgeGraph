from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from typing import Dict, List, Any
import json

app = FastAPI(title="Wikipedia Scraper API", version="1.0.0")

BASE_URL = "https://tr.wikipedia.org"


# Request Model
class WikiURLRequest(BaseModel):
    url: str


# Custom JSON Response with indentation
class PrettyJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=4,
            separators=(", ", ": "),
        ).encode("utf-8")
    
    media_type = "application/json; charset=utf-8"


# Helper Functions
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
        
        # ÇÖZÜM: from_encoding parametresi ile UTF-8 zorunlu kıl
        soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
        
        return soup
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Sayfa yüklenemedi: {str(e)}")


def metni_temizle(text):
    """
    Metni temizler: referansları, fazla boşlukları kaldırır.
    """
    if not text:
        return ""
    
    # Referans numaralarını kaldır: [1], [107], [ 5 ] gibi
    text = re.sub(r'\[\s*\d+\s*\]', '', text)
    
    # Ardışık referansları da temizle: [1][2][3]
    text = re.sub(r'(\[\s*\d+\s*\])+', '', text)
    
    # Fazla boşlukları tek boşluğa indir
    text = re.sub(r'\s+', ' ', text)
    
    # Baş ve sondaki boşlukları kaldır
    text = text.strip()
    
    return text


def vcard_verilerini_cek(soup):
    """Sayfadaki sağ bilgi kutusundaki (infobox) verileri çeker."""
    vcard = soup.select_one('.vcard')
    if not vcard:
        return {}

    vcard_dict = {}
    key_counter = {}
    rows = vcard.select('tr')

    for row in rows:
        th = row.find('th')
        td = row.find('td')
        
        if not th and not td:
            continue
            
        if th and not td:
            key = th.get_text(strip=True)
            if key:
                if key in key_counter:
                    key_counter[key] += 1
                    numbered_key = f"{key} ({key_counter[key]})"
                else:
                    key_counter[key] = 1
                    numbered_key = key
                
                if numbered_key not in vcard_dict:
                    vcard_dict[numbered_key] = ""
            continue
        
        if not th and td:
            if vcard_dict:
                last_key = list(vcard_dict.keys())[-1]
                text = td.get_text(separator=' ', strip=True)
                text = metni_temizle(text)
                
                if vcard_dict[last_key]:
                    vcard_dict[last_key] += " " + text
                else:
                    vcard_dict[last_key] = text
            continue

        key = th.get_text(strip=True)
        if not key:
            continue
            
        value = td.get_text(separator=' ', strip=True)
        value = metni_temizle(value)
        
        if key in key_counter:
            key_counter[key] += 1
            final_key = f"{key} ({key_counter[key]})"
        else:
            key_counter[key] = 1
            final_key = key
        
        vcard_dict[final_key] = value

    return vcard_dict


def paragraf_listesi_cek(soup):
    """Paragrafları liste olarak döner."""
    paragraflar = soup.select('#mw-content-text p')
    
    paragraf_liste = []
    
    for p in paragraflar:
        text = p.get_text(separator=' ', strip=True)
        if not text:
            continue
        
        # Metni temizle
        text = metni_temizle(text)
        
        if text:  # Temizleme sonrası boş olabilir
            paragraf_liste.append(text)
    
    return paragraf_liste


def cumlelere_ayir(metin):
    """Metni cümlelere ayırır."""
    if not metin or not isinstance(metin, str):
        return []

    # Sayılar ve kısaltmalardaki noktaları koru
    temp_text = re.sub(r'(\d+)\.(\s*[a-zA-ZçğıöşüÇĞİÖŞÜ])', r'\1[[DOT]]\2', metin)
    temp_text = re.sub(r'\b([A-Za-zÇĞİÖŞÜçğıöşü]{1,4})\.(\s*[a-zA-ZçğıöşüÇĞİÖŞÜ])', r'\1[[DOT]]\2', temp_text)

    # Cümleleri ayır
    raw_sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ])', temp_text.strip())

    # Yer tutucuları geri koy
    final_sentences = []
    for s in raw_sentences:
        s = s.replace("[[DOT]]", ".")
        s = s.strip()
        if s:
            final_sentences.append(s)

    return final_sentences


def baslik_cek(soup):
    """Sayfa başlığını çeker."""
    return (
        soup.title.string.replace(" - Vikipedi", "").strip()
        if soup.title else "Başlık Bulunamadı"
    )


# ENDPOINT 1: Full (Card + Paragraflar)
@app.post("/scrape/full", response_class=PrettyJSONResponse)
async def scrape_full(request: WikiURLRequest):
    """
    Wikipedia sayfasını Card ve paragraflar halinde scrape eder.
    
    - **Card**: Sağdaki bilgi kutusu
    - **Main**: Paragraflar listesi
    """
    soup = web_scraping_yap(request.url)
    baslik = baslik_cek(soup)
    card = vcard_verilerini_cek(soup)
    paragraflar = paragraf_listesi_cek(soup)
    
    main = [
        {"id": i+1, "paragraph": p}
        for i, p in enumerate(paragraflar)
    ]
    
    return {
        "Title": baslik,
        "Card": card,
        "Main": main
    }


# ENDPOINT 2: Single Text (Tek metin bloğu)
@app.post("/scrape/single", response_class=PrettyJSONResponse)
async def scrape_single(request: WikiURLRequest):
    """
    Wikipedia sayfasını tek bir metin bloğu olarak scrape eder.
    
    - **Main**: Tüm paragraflar birleştirilmiş tek metin
    - **block_count**: 1
    """
    soup = web_scraping_yap(request.url)
    baslik = baslik_cek(soup)
    paragraflar = paragraf_listesi_cek(soup)
    
    # Tüm paragrafları birleştir
    tek_metin = " ".join(paragraflar)
    
    return {
        "Title": baslik,
        "Main": tek_metin,
        "block_count": 1
    }


# ENDPOINT 3: Paragraphs (Paragraflara bölünmüş)
@app.post("/scrape/paragraphs", response_class=PrettyJSONResponse)
async def scrape_paragraphs(request: WikiURLRequest):
    """
    Wikipedia sayfasını paragraflar halinde scrape eder.
    
    - **Main**: Her paragraf ayrı bir blok
    - **block_count**: Paragraf sayısı
    """
    soup = web_scraping_yap(request.url)
    baslik = baslik_cek(soup)
    paragraflar = paragraf_listesi_cek(soup)
    
    main = [
        {"id": i+1, "text": p}
        for i, p in enumerate(paragraflar)
    ]
    
    return {
        "Title": baslik,
        "Main": main,
        "block_count": len(main)
    }


# ENDPOINT 4: Sentences (Cümlelere bölünmüş)
@app.post("/scrape/sentences", response_class=PrettyJSONResponse)
async def scrape_sentences(request: WikiURLRequest):
    """
    Wikipedia sayfasını cümlelere bölerek scrape eder.
    
    - **Main**: Her cümle ayrı bir blok
    - **block_count**: Cümle sayısı
    """
    soup = web_scraping_yap(request.url)
    baslik = baslik_cek(soup)
    paragraflar = paragraf_listesi_cek(soup)
    
    # Tüm paragrafları cümlelere ayır
    tum_cumleler = []
    for paragraf in paragraflar:
        cumleler = cumlelere_ayir(paragraf)
        tum_cumleler.extend(cumleler)
    
    main = [
        {"id": i+1, "sentence": c}
        for i, c in enumerate(tum_cumleler)
    ]
    
    return {
        "Title": baslik,
        "Main": main,
        "block_count": len(main)
    }


# Ana sayfa ve dokümantasyon
@app.get("/", response_class=PrettyJSONResponse)
async def root():
    return {
        "message": "Wikipedia Scraper API",
        "version": "1.0.0",
        "endpoints": {
            "1": "/scrape/full - Card + Paragraflar",
            "2": "/scrape/single - Tek metin bloğu",
            "3": "/scrape/paragraphs - Paragraflara bölünmüş",
            "4": "/scrape/sentences - Cümlelere bölünmüş"
        },
        "documentation": "/docs"
    }


# Uygulama çalıştırma
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)