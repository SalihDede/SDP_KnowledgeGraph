#!/usr/bin/env python3
"""
Archive.org sayfasından PDF'leri indir (BeautifulSoup)
"""
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import time

def scrape_and_download_pdfs():
    """Archive.org'dan PDF linklerini çıkart ve indir"""

    archive_url = "https://archive.org/details/tatillerdetatliugrasib.c.dergisi/"
    output_folder = Path("pdfs_downloaded")
    output_folder.mkdir(exist_ok=True)

    print(f"📄 {archive_url} taranıyor...\n")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(archive_url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # .download-pill sınıfından PDF linklerini çıkart
        pdf_links = []

        # .download-pill sınıfını bul
        download_pills = soup.find_all('a', class_='download-pill')

        print(f"Tarandı: {len(download_pills)} download pill")

        for pill in download_pills:
            href = pill.get('href', '')
            text = pill.get_text(strip=True)

            # PDF linkini kontrol et
            if '.pdf' in href.lower():
                # Mutlak URL'ye dönüştür
                if href.startswith('//'):
                    full_url = f"https:{href}"
                elif href.startswith('/'):
                    full_url = f"https://archive.org{href}"
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue

                filename = href.split('/')[-1].split('?')[0]

                # Duplikat kontrolü
                if not any(item['url'] == full_url for item in pdf_links):
                    pdf_links.append({
                        'url': full_url,
                        'filename': filename
                    })

        print(f"Bulundu: {len(pdf_links)} PDF\n")

        if not pdf_links:
            print("❌ PDF bulunamadı!")
            return

        # İndirme başla
        print(f"📥 İndiriliyor...\n")

        downloaded = 0
        failed = 0

        for i, item in enumerate(pdf_links, 1):
            url = item['url']
            filename = item['filename']
            output_path = output_folder / filename

            # Zaten var mı kontrol et
            if output_path.exists():
                size_mb = output_path.stat().st_size / (1024 * 1024)
                print(f"✓ [{i}/{len(pdf_links)}] {filename} ({size_mb:.1f} MB) - Zaten var")
                downloaded += 1
                continue

            print(f"⬇ [{i}/{len(pdf_links)}] {filename}...", end=" ", flush=True)

            try:
                pdf_response = requests.get(url, headers=headers, timeout=30, stream=True)
                pdf_response.raise_for_status()

                # Dosya boyutunu göster
                total_size = int(pdf_response.headers.get('content-length', 0))

                with open(output_path, 'wb') as f:
                    downloaded_size = 0
                    for chunk in pdf_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded_size += len(chunk)

                file_size_mb = output_path.stat().st_size / (1024 * 1024)
                print(f"✓ ({file_size_mb:.1f} MB)")
                downloaded += 1

                time.sleep(0.3)

            except Exception as e:
                print(f"✗ {str(e)[:40]}")
                failed += 1
                if output_path.exists():
                    output_path.unlink()

            # Progress
            if i % 20 == 0:
                print(f"   ➜ İlerleme: {i}/{len(pdf_links)}")

        print(f"\n✅ Tamamlandı!")
        print(f"   İndirilen: {downloaded}")
        print(f"   Başarısız: {failed}")
        print(f"   Klasör: {output_folder.absolute()}")

    except Exception as e:
        print(f"❌ Hata: {e}")

if __name__ == "__main__":
    scrape_and_download_pdfs()
