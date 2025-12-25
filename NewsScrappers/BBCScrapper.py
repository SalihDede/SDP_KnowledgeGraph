import requests
from bs4 import BeautifulSoup
import time
import random

def get_soup(url, headers):
    """Verilen URL'e istek atıp BeautifulSoup objesi döner."""
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")
    except Exception as e:
        print(f"⚠️ Hata (Bağlantı): {url} - {e}")
        return None

def collect_article_links(start_url, base_url, headers, max_topics=5):
    """Ana sayfayı ve konu sayfalarını tarayarak haber linklerini toplar."""
    print(f"🕷️ Link toplama işlemi başlıyor: {start_url}")
    
    soup = get_soup(start_url, headers)
    if not soup:
        return []

    article_links = set()
    topic_links = set()

    # 1. Ana sayfadaki tüm linkleri tara
    for link in soup.find_all("a", href=True):
        href = link["href"]
        full_url = href if href.startswith("http") else base_url + href
        
        # Haber linki mi?
        if "/turkce/articles/" in href:
            article_links.add(full_url)
        # Konu/Kategori linki mi? (Örn: /turkce/topics/...)
        elif "/turkce/topics/" in href:
            topic_links.add(full_url)

    print(f"✅ Ana sayfada {len(article_links)} haber ve {len(topic_links)} kategori bulundu.")

    # 2. Bulunan kategorilerin içine girip oradan da haber topla
    # (Sonsuz döngüye girmemek için max_topics ile sınırlıyoruz)
    for i, topic_url in enumerate(list(topic_links)[:max_topics]):
        print(f"   📂 Kategori taranıyor ({i+1}/{max_topics}): {topic_url}")
        t_soup = get_soup(topic_url, headers)
        if t_soup:
            count_before = len(article_links)
            for link in t_soup.find_all("a", href=True):
                href = link["href"]
                if "/turkce/articles/" in href:
                    full_url = href if href.startswith("http") else base_url + href
                    article_links.add(full_url)
            print(f"      -> {len(article_links) - count_before} yeni haber bulundu.")
        time.sleep(random.uniform(0.5, 1.5)) # Nezaket beklemesi

    return list(article_links)

def scrape_bbc_comprehensive(output_file="NewsScrappers/bbc_turkce_genis_arsiv.txt", limit=20):
    base_url = "https://www.bbc.com"
    start_url = "https://www.bbc.com/turkce"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # 1. Adım: Linkleri Topla
    all_links = collect_article_links(start_url, base_url, headers, max_topics=4)
    
    # Limitleme
    target_links = all_links[:limit]
    print(f"\n🎯 Toplam {len(all_links)} eşsiz haber bulundu. Hedeflenen {len(target_links)} tanesi çekilecek.\n")
    print("="*60)

    # 2. Adım: Haberleri Çek ve Kaydet
    with open(output_file, "w", encoding="utf-8") as f:
        success_count = 0
        for i, url in enumerate(target_links, 1):
            print(f"[{i}/{len(target_links)}] İçerik indiriliyor: {url}")
            
            soup = get_soup(url, headers)
            if not soup:
                continue

            try:
                # Başlık
                headline = soup.find("h1")
                headline_text = headline.get_text().strip() if headline else "Başlık Bulunamadı"
                
                # İçerik
                main_content = soup.find("main")
                text_content = ""
                if main_content:
                    # BBC makalelerinde metinler genellikle paragraf (p) veya liste (li) içindedir
                    blocks = main_content.find_all(["p", "h2", "ul"]) 
                    content_parts = []
                    for block in blocks:
                        # Gereksiz menü öğelerini filtrele
                        if block.name == "ul" and ("class" in block.attrs and "bbc" in str(block.attrs["class"])):
                            continue
                        content_parts.append(block.get_text().strip())
                    text_content = "\n\n".join(content_parts)
                
                if text_content:
                    f.write(f"BAŞLIK: {headline_text}\n")
                    f.write(f"KAYNAK: {url}\n")
                    f.write("-" * 20 + "\n")
                    f.write(text_content)
                    f.write("\n\n" + "=" * 50 + "\n\n")
                    success_count += 1
                else:
                    print(f"   ⚠️ İçerik boş, atlanıyor.")

            except Exception as e:
                print(f"   ❌ Hata: {e}")
            
            # Sunucuyu yormamak için rastgele bekleme
            time.sleep(random.uniform(0.8, 2.0))

    print(f"\n🎉 İşlem tamamlandı! {success_count} haber '{output_file}' dosyasına kaydedildi.")

if __name__ == "__main__":
    # limit değerini artırarak (örn: 50, 100) daha fazla haber çekebilirsiniz
    scrape_bbc_comprehensive(limit=20)