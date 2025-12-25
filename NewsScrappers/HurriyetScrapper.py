import requests
from bs4 import BeautifulSoup
import time
import random
import re

def get_soup(url, headers):
    """Verilen URL'e istek atıp BeautifulSoup objesi döner."""
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")
    except Exception as e:
        print(f"⚠️ Hata (Bağlantı): {url} - {e}")
        return None

def is_article_link(href):
    """Linkin bir haber makalesi olup olmadığını kontrol eder."""
    if not href:
        return False
    
    # İstenmeyen bölümler
    exclude_list = ['/video/', '/galeri/', '/yazarlar/', '/astroloji/', '/yerel-haberler/', '/tv-rehberi/']
    if any(ex in href for ex in exclude_list):
        return False
        
    # Hürriyet haber linkleri genellikle bir ID numarası ile biter (örn: ...-42123456)
    # veya standart kategori yollarını içerir.
    # En basit kontrol: Link uzunluğu ve sayısal ID kontrolü
    if re.search(r'\d{7,}', href): # En az 7 haneli bir sayı varsa muhtemelen haber ID'sidir
        return True
        
    return False

def collect_hurriyet_links(base_url, headers, max_categories=4):
    """Ana sayfayı ve kategorileri tarayarak haber linklerini toplar."""
    print(f"🕷️ Link toplama işlemi başlıyor: {base_url}")
    
    soup = get_soup(base_url, headers)
    if not soup:
        return []

    article_links = set()
    category_links = []

    # Hürriyet ana menüdeki kategorileri bulalım
    # Genellikle nav bar içindedir veya manuel listeleme daha güvenlidir
    target_categories = ['gundem', 'dunya', 'ekonomi', 'teknoloji', 'spor', 'kelebek']
    
    for cat in target_categories:
        category_links.append(f"{base_url}/{cat}")

    print(f"✅ Taranacak kategoriler: {', '.join(target_categories)}")

    # Kategorileri gez
    for i, cat_url in enumerate(category_links[:max_categories]):
        print(f"   📂 Kategori taranıyor ({i+1}/{max_categories}): {cat_url}")
        c_soup = get_soup(cat_url, headers)
        
        if c_soup:
            count_before = len(article_links)
            # Sayfadaki tüm linkleri tara
            for link in c_soup.find_all("a", href=True):
                href = link["href"]
                
                # Linki tam URL yap
                if href.startswith("//"):
                    full_url = "https:" + href
                elif href.startswith("/"):
                    full_url = base_url + href
                elif href.startswith("http"):
                    full_url = href
                else:
                    continue

                # Sadece Hürriyet domaini içindeyse ve haber linki kriterine uyuyorsa al
                if "hurriyet.com.tr" in full_url and is_article_link(full_url):
                    article_links.add(full_url)
            
            print(f"      -> {len(article_links) - count_before} yeni haber bulundu.")
            
        time.sleep(random.uniform(1.0, 2.0))

    return list(article_links)

def scrape_hurriyet(output_file="NewsScrappers/hurriyet_haberler.txt", limit=20):
    base_url = "https://www.hurriyet.com.tr"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }

    # 1. Adım: Linkleri Topla
    all_links = collect_hurriyet_links(base_url, headers)
    
    # Linkleri karıştır ki hep aynı sırayla olmasın (çeşitlilik için)
    import random
    random.shuffle(all_links)
    
    target_links = all_links[:limit]
    print(f"\n🎯 Toplam {len(all_links)} potansiyel haber bulundu. {len(target_links)} tanesi seçildi ve işlenecek.\n")
    print("="*60)

    # 2. Adım: İçerikleri Çek
    with open(output_file, "w", encoding="utf-8") as f:
        success_count = 0
        for i, url in enumerate(target_links, 1):
            print(f"[{i}/{len(target_links)}] İşleniyor: {url}")
            
            soup = get_soup(url, headers)
            if not soup:
                continue

            try:
                # --- Başlık Çıkarma ---
                # Hürriyet'te başlık genellikle h1 sınıfı "news-detail-title" veya benzeridir
                headline = soup.find("h1")
                headline_text = headline.get_text().strip() if headline else "Başlık Bulunamadı"

                # --- İçerik Çıkarma ---
                text_content = ""
                
                # Hürriyet makale gövdesi için olası container sınıfları
                content_div = soup.find("div", class_="news-content") or \
                              soup.find("div", class_="reading-content") or \
                              soup.find("article")
                
                if content_div:
                    # Gereksiz öğeleri (reklam, "bunu da oku" vb.) temizle
                    for junk in content_div.find_all(["script", "style", "div", "iframe"]):
                        # Bazı div'ler metin içerebilir ama genellikle reklam/widget container'ıdır.
                        # Çok agresif silmemek için class kontrolü yapılabilir ama basitlik adına metne odaklanalım.
                        pass 

                    paragraphs = content_div.find_all("p")
                    # Eğer p tagleri yoksa (bazen sadece br ile ayrılır), div metnini al
                    if paragraphs:
                        content_parts = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20]
                        text_content = "\n\n".join(content_parts)
                    else:
                         text_content = content_div.get_text(separator="\n").strip()
                
                # İçerik çok kısaysa (muhtemelen galeri veya video sayfasıdır), kaydetme
                if len(text_content) < 100:
                    print(f"   ⚠️ İçerik çok kısa veya bulunamadı, atlanıyor.")
                    continue

                # --- Dosyaya Yaz ---
                f.write(f"BAŞLIK: {headline_text}\n")
                f.write(f"KAYNAK: {url}\n")
                f.write("-" * 20 + "\n")
                f.write(text_content)
                f.write("\n\n" + "=" * 50 + "\n\n")
                
                success_count += 1
                print(f"   ✅ Kaydedildi.")

            except Exception as e:
                print(f"   ❌ Ayrıştırma hatası: {e}")
            
            time.sleep(random.uniform(1.0, 2.5))

    print(f"\n🎉 İşlem tamamlandı! {success_count} haber '{output_file}' dosyasına kaydedildi.")

if __name__ == "__main__":
    scrape_hurriyet(limit=100)