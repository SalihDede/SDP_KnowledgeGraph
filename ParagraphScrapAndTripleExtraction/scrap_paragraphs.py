import requests
from bs4 import BeautifulSoup
import json
import concurrent.futures
import re
import os
import urllib.parse
import time  # Bekleme süreleri için eklendi

def clean_wiki_text(text):
    """Metin içindeki Wikipedia referanslarını ve gereksiz boşlukları temizler."""
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\[kaynak belirtilmeli\]', '', text)
    return text.strip()

def get_random_wiki_titles(total_pages=150000, titles_file="wiki_titles_150k.json"):
    """
    Eğer belirtilen JSON dosyası varsa başlıkları oradan çeker (Sample işlemini atlar).
    Yoksa Wikipedia API'den çeker ve bu JSON dosyasına kaydeder.
    """
    # 1. KONTROL: Kayıtlı başlık dosyası var mı?
    if os.path.exists(titles_file):
        print(f"\n[BİLGİ] '{titles_file}' dosyası bulundu. API'ye bağlanmadan lokalden okunuyor...")
        with open(titles_file, 'r', encoding='utf-8') as f:
            titles = json.load(f)
        print(f"Toplam {len(titles)} başlık başarıyla hafızaya alındı.\n")
        return titles[:total_pages]

    # 2. EĞER DOSYA YOKSA: API'den çekmeye başla
    titles = set()
    api_url = "https://tr.wikipedia.org/w/api.php"
    
    print(f"\n[BİLGİ] Lokal dosya bulunamadı. Wikipedia API'den {total_pages} adet başlık toplanıyor.")
    print("API limitlerine takılmamak için 150.000 başlık toplamak ortalama 45-50 dakika sürebilir...")
    
    headers = {
        'User-Agent': 'TurkishKGPipeline/1.0 (Knowledge Graph Construction Project) python-requests/2.x'
    }
    
    while len(titles) < total_pages:
        params = {
            "action": "query",
            "format": "json",
            "list": "random",
            "rnnamespace": 0, 
            "rnlimit": 50 
        }
        
        try:
            response = requests.get(api_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 429:
                print("\n[UYARI] API sınırına ulaşıldı (HTTP 429). 5 saniye dinleniliyor...")
                time.sleep(15)
                continue
                
            response.raise_for_status()
            data = response.json()
            
            for page in data['query']['random']:
                titles.add(page['title'])
                
            if len(titles) % 1000 == 0 or len(titles) >= total_pages:
                print(f"Toplanan başlık sayısı: {len(titles)} / {total_pages}")
            
            time.sleep(2)
                
        except Exception as e:
            print(f"[HATA] API isteği başarısız oldu: {e}")
            time.sleep(2)
            
    titles_list = list(titles)[:total_pages]
    
    # 3. KAYIT AŞAMASI: Çekilen başlıkları JSON'a kaydet
    with open(titles_file, 'w', encoding='utf-8') as f:
        json.dump(titles_list, f, ensure_ascii=False, indent=2)
    print(f"\n[BAŞARILI] {total_pages} sayfa başlığı '{titles_file}' dosyasına kaydedildi.\n")
    
    return titles_list

def scrape_wiki_page(page_title, max_retries=3):
    """
    Sayfa başlığını alır, içeriğini okur. 429 hatası alırsa pes etmez, 
    bekleyip tekrar dener (Maksimum 3 deneme).
    """
    formatted_title = page_title.replace(" ", "_")
    url = f"https://tr.wikipedia.org/wiki/{formatted_title}"
    
    headers = {
        'User-Agent': 'TurkishKGPipeline/1.0 (Knowledge Graph Construction Project) python-requests/2.x'
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 429:
                sleep_time = 3 * (attempt + 1)
                time.sleep(sleep_time)
                continue 
                
            response.raise_for_status()
            break 
            
        except requests.exceptions.RequestException:
            if attempt == max_retries - 1:
                return [] 
            time.sleep(2)
            continue
    else:
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    
    content_div = soup.find('div', id='mw-content-text')
    if not content_div:
        return []

    paragraphs = content_div.find_all('p')
    
    page_data = []
    p_num = 1
    
    for p in paragraphs:
        text = clean_wiki_text(p.get_text())
        
        if len(text.split()) > 5: 
            page_data.append({
                "wikipedia_page": response.url,
                "paragraph_number": p_num,
                "paragraph_text": text
            })
            p_num += 1
            
    return page_data

def build_benchmark_dataset(output_filename="kg_benchmark_dataset.json", total_pages=150000, max_workers=10):
    """Ana orkestrasyon fonksiyonu."""
    
    page_titles = get_random_wiki_titles(total_pages=total_pages)
    
    all_data = []
    print(f"Toplam {len(page_titles)} sayfa için eşzamanlı paragraf çekimi başlatılıyor...")
    print("(İlerleme her 1000 sayfada bir gösterilecektir.)\n")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_title = {executor.submit(scrape_wiki_page, title): title for title in page_titles}
        
        completed_count = 0
        for future in concurrent.futures.as_completed(future_to_title):
            completed_count += 1
            
            try:
                data = future.result()
                if data:
                    all_data.extend(data)
                    
                # Hedef 150k olduğu için logları 1000'de bire seyrelttim
                if completed_count % 1000 == 0 or completed_count == total_pages:
                    print(f"İşlenen sayfa: {completed_count}/{total_pages} | Çıkartılan toplam paragraf: {len(all_data)}")
                    
            except Exception:
                pass 

    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
        
    print(f"\nİşlem TAMAMLANDI! Toplam {len(all_data)} paragraf '{output_filename}' adlı dosyaya kaydedildi.")

if __name__ == "__main__":
    build_benchmark_dataset(
        output_filename="paragraph_dataset_150k.json",
        total_pages=150000, # 150k hedefi burada belirlendi
        max_workers=10 
    )