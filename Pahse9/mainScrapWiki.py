import json
import time
import os
import pandas as pd
import re
from datetime import datetime
from urllib.parse import urljoin, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue
from scrapWikipedia import veri_cek_ve_json_olarak_dondur
from getEntityUrlFreq import analiz_yap, e_u_total_cikti
from entityFrequencyAnalyzer import EntityFrequencyAnalyzer
import sys

# ============================================================================
# GELİŞMİŞ LOGGER SİSTEMİ
# ============================================================================
Paralel_worker_max_limit = 1000


class ColoredLogger:
    """Renkli ve yapılandırılmış loglama sistemi"""
    
    # ANSI renk kodları
    COLORS = {
        'RESET': '\033[0m',
        'BOLD': '\033[1m',
        'RED': '\033[91m',
        'GREEN': '\033[92m',
        'YELLOW': '\033[93m',
        'BLUE': '\033[94m',
        'MAGENTA': '\033[95m',
        'CYAN': '\033[96m',
        'WHITE': '\033[97m',
        'GRAY': '\033[90m'
    }
    
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")
        self.lock = threading.Lock()
        
    def write(self, message):
        with self.lock:
            self.terminal.write(message)
            # Dosyaya yazarken renk kodlarını temizle
            clean_msg = self._strip_colors(message)
            self.log.write(clean_msg)
    
    def flush(self):
        self.terminal.flush()
        self.log.flush()
    
    def _strip_colors(self, text):
        """ANSI renk kodlarını temizle"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def success(self, msg, indent=0):
        """Başarı mesajı (yeşil)"""
        prefix = "  " * indent
        self.write(f"{self.COLORS['GREEN']}✓ {msg}{self.COLORS['RESET']}\n")
    
    def error(self, msg, indent=0, details=None):
        """Hata mesajı (kırmızı)"""
        prefix = "  " * indent
        self.write(f"{self.COLORS['RED']}✗ {msg}{self.COLORS['RESET']}\n")
        if details:
            self.write(f"{self.COLORS['GRAY']}  └─ Detay: {details}{self.COLORS['RESET']}\n")
    
    def warning(self, msg, indent=0):
        """Uyarı mesajı (sarı)"""
        prefix = "  " * indent
        self.write(f"{self.COLORS['YELLOW']}⚠ {msg}{self.COLORS['RESET']}\n")
    
    def info(self, msg, indent=0):
        """Bilgi mesajı (mavi)"""
        prefix = "  " * indent
        self.write(f"{self.COLORS['CYAN']}ℹ {msg}{self.COLORS['RESET']}\n")
    
    def progress(self, msg, indent=0):
        """İlerleme mesajı (magenta)"""
        prefix = "  " * indent
        self.write(f"{self.COLORS['MAGENTA']}▶ {msg}{self.COLORS['RESET']}\n")
    
    def section(self, title, char="=", width=80):
        """Bölüm başlığı"""
        line = char * width
        self.write(f"\n{self.COLORS['BOLD']}{self.COLORS['CYAN']}{line}{self.COLORS['RESET']}\n")
        self.write(f"{self.COLORS['BOLD']}{self.COLORS['WHITE']}{title.center(width)}{self.COLORS['RESET']}\n")
        self.write(f"{self.COLORS['BOLD']}{self.COLORS['CYAN']}{line}{self.COLORS['RESET']}\n\n")
    
    def subsection(self, title, indent=0):
        """Alt bölüm başlığı"""
        prefix = "  " * indent
        self.write(f"\n{prefix}{self.COLORS['BOLD']}{self.COLORS['BLUE']}┌─ {title} ─┐{self.COLORS['RESET']}\n")
    
    def url_log(self, url, status, depth, page_num, details=None):
        """URL işleme logu - detaylı ve yapılandırılmış"""
        indent = "  " * (depth + 1)
        
        # URL'yi kısalt
        display_url = url if len(url) <= 70 else url[:67] + "..."
        
        # Durum rengini belirle
        if status == "success":
            color = self.COLORS['GREEN']
            icon = "✓"
        elif status == "error":
            color = self.COLORS['RED']
            icon = "✗"
        elif status == "skip":
            color = self.COLORS['YELLOW']
            icon = "⊘"
        else:
            color = self.COLORS['GRAY']
            icon = "○"
        
        # Ana log
        self.write(f"\n{indent}{color}[D{depth}:P{page_num}] {icon} {display_url}{self.COLORS['RESET']}\n")
        
        # Detayları alt satırda göster
        if details:
            for key, value in details.items():
                self.write(f"{indent}  │ {self.COLORS['GRAY']}{key}: {value}{self.COLORS['RESET']}\n")
        
        self.write(f"{indent}  └{'─' * 70}\n")

# Global logger
logger = ColoredLogger("scraping_log.txt")
sys.stdout = logger
sys.stderr = logger

# ============================================================================
# YARDIMCI FONKSİYONLAR
# ============================================================================

def guvenli_dosya_adi(metin, max_uzunluk=30):
    """Windows için güvenli dosya adı oluşturur"""
    if not metin:
        return "Bilinmeyen"
    
    temiz = re.sub(r'[<>:"/\\|?*"\']', '_', metin)
    temiz = re.sub(r'[\r\n\t]', '_', temiz)
    temiz = re.sub(r'[&=#+%]', '_', temiz)
    temiz = re.sub(r'_+', '_', temiz)
    temiz = temiz.strip('._')
    
    if len(temiz) > max_uzunluk:
        temiz = temiz[:max_uzunluk]
    
    if not temiz or temiz.isspace():
        temiz = "Sayfa"
    
    return temiz

# Global değişkenler
lock = threading.Lock()
sayfa_counter = 0
hata_sayaci = {'network': 0, 'parse': 0, 'file': 0, 'other': 0}

derinlik_stats = {}


def tek_sayfa_isle(url_derinlik_tuple, entity_analyzer, ziyaret_edilenler, bekleme_suresi=1):
    """Tek sayfayı paralel olarak işler - gelişmiş loglama ile"""
    global sayfa_counter, hata_sayaci, derinlik_stats
    
    url, derinlik = url_derinlik_tuple
    
    with lock:
        sayfa_counter += 1
        current_page_num = sayfa_counter
        if url in ziyaret_edilenler:
            # Skip istatistiğini güncelle
            if derinlik not in derinlik_stats:
                derinlik_stats[derinlik] = {'basarili': 0, 'basarisiz': 0, 'skip': 0, 'unique_pairs': 0, 'sure': 0, 'baslangic': None}
            derinlik_stats[derinlik]['skip'] += 1
            
            logger.url_log(url, "skip", derinlik, current_page_num, 
                          {"Durum": "Zaten işlendi"})
            return None
        ziyaret_edilenler.add(url)
    
    details = {}
    
    try:
        logger.subsection(f"Sayfa #{current_page_num} İşleniyor", indent=derinlik)
        
        # 1️⃣ Sayfayı scrap et
        logger.progress(f"URL çekiliyor...", indent=derinlik+1)
        scrape_start = time.time()
        
        veri = veri_cek_ve_json_olarak_dondur(url)
        scrape_time = time.time() - scrape_start
        
        if "hata" in veri:
            with lock:
                hata_sayaci['network'] += 1
            logger.url_log(url, "error", derinlik, current_page_num, {
                "Hata Tipi": "Network/Parse",
                "Mesaj": veri['hata'],
                "Süre": f"{scrape_time:.2f}s"
            })
            return None
        
        details["Scrape Süresi"] = f"{scrape_time:.2f}s"
        details["Başlık"] = veri.get('Title', 'N/A')[:50]

        # 2️⃣ JSON kaydet
        sayfa_adi = guvenli_dosya_adi(veri.get('Title', f'Sayfa{current_page_num}'))
        json_dosya = f"Wiki_D{derinlik}_{current_page_num}_{sayfa_adi}.json"
        
        try:
            with lock:
                with open(json_dosya, "w", encoding="utf-8") as f:
                    json.dump(veri, f, indent=4, ensure_ascii=False)
            details["JSON Dosya"] = json_dosya
            logger.success(f"JSON kaydedildi: {json_dosya}", indent=derinlik+1)
        except Exception as e:
            with lock:
                hata_sayaci['file'] += 1
            logger.error(f"JSON kayıt hatası", indent=derinlik+1, details=str(e))
            return None

        # 3️⃣ Entity analizi
        logger.progress(f"Entity analizi yapılıyor...", indent=derinlik+1)
        csv_dosya = f"E_U_D{derinlik}_{current_page_num}_{sayfa_adi}.csv"
        
        try:
            df = analiz_yap(json_dosya, cikti_csv_adi=csv_dosya)
            
            if df is not None and not df.empty:
                details["Entity-URL Çifti"] = len(df)
                logger.success(f"{len(df)} Entity-URL çifti bulundu", indent=derinlik+1)
            else:
                df = pd.DataFrame(columns=["E", "U", "Frekans", "Kaynak_IDler"])
                details["Entity-URL Çifti"] = 0
                logger.warning(f"Entity analizi boş sonuç döndü", indent=derinlik+1)
        except Exception as e:
            with lock:
                hata_sayaci['parse'] += 1
            logger.error(f"Entity analizi hatası", indent=derinlik+1, details=str(e))
            df = pd.DataFrame(columns=["E", "U", "Frekans", "Kaynak_IDler"])

        # 4️⃣ Kümülatif entity analizi
        try:
            entity_result = entity_analyzer.analyze_json_file(json_dosya)
            if "error" not in entity_result:
                details["Unique Entity"] = entity_result['unique_entities']
                details["Unique Pairs"] = entity_result['unique_pairs']
                logger.success(f"{entity_result['unique_entities']} entity, "
                             f"{entity_result['unique_pairs']} çift", indent=derinlik+1)
        except Exception as e:
            logger.warning(f"Kümülatif analiz hatası: {str(e)[:50]}", indent=derinlik+1)

        # 5️⃣ Yeni linkler bul
        yeni_linkler = set()
        if not df.empty:
            # Önceden filtrele ve gereksiz kontrolleri kaldır
            gecersiz_parcalar = ('action=edit', 'redlink=1', '/w/index.php?', '#', 'oldid=', 'diff=')
    
            for _, satir in df.iterrows():
                if "U" in satir and isinstance(satir["U"], str):
                    url = satir["U"]
            
                # Sadece dış parantezleri temizle
                if url.startswith("(") and url.endswith(")"):
                    clean_url = url[1:-1]  # İlk ve son karakteri çıkar
                else:
                    clean_url = url
                
                # Wikipedia kontrolü ve geçersiz link kontrolü
                if (clean_url.startswith("https://tr.wikipedia.org") and 
                    not any(parcacik in clean_url for parcacik in gecersiz_parcalar)):
                    yeni_linkler.add(clean_url)
        
        details["Yeni Link"] = len(yeni_linkler)
        logger.info(f"{len(yeni_linkler)} geçerli link bulundu", indent=derinlik+1)
        
        # Rate limiting
        time.sleep(bekleme_suresi)
        
        # Başarı logu
        logger.url_log(url, "success", derinlik, current_page_num, details)
        
        # Başarılı istatistiğini güncelle
        with lock:
            if derinlik not in derinlik_stats:
                derinlik_stats[derinlik] = {'basarili': 0, 'basarisiz': 0, 'skip': 0, 'unique_pairs': 0, 'sure': 0, 'baslangic': None}
            derinlik_stats[derinlik]['basarili'] += 1
            # Entity-URL çifti sayısını ekle
            if df is not None and not df.empty:
                derinlik_stats[derinlik]['unique_pairs'] += len(df)
        
        return {
            'json_dosya': json_dosya,
            'df': df,
            'yeni_linkler': yeni_linkler,
            'derinlik': derinlik,
            'url': url
        }
        
    except Exception as e:
        with lock:
            hata_sayaci['other'] += 1
            # Başarısız istatistiğini güncelle
            if derinlik not in derinlik_stats:
                derinlik_stats[derinlik] = {'basarili': 0, 'basarisiz': 0, 'skip': 0, 'unique_pairs': 0, 'sure': 0, 'baslangic': None}
            derinlik_stats[derinlik]['basarisiz'] += 1
            
        logger.url_log(url, "error", derinlik, current_page_num, {
            "Hata Tipi": "Bilinmeyen",
            "Mesaj": str(e)[:100]
        })
        return None

# ============================================================================
# ANA FONKSİYON
# ============================================================================

BASE_URL = "https://tr.wikipedia.org"

def derin_scrap(root_urls, max_depth=2, bekleme_suresi=1, paralel_worker=3):
    """Wikipedia'dan derin scraping - gelişmiş loglama ile

    root_urls: tek bir URL string veya URL listesi
    """

    # Tek URL verilirse listeye çevir
    if isinstance(root_urls, str):
        root_urls = [root_urls]

    logger.section("🚀 WIKIPEDIA ENTITY FREKANS ANALİZ SİSTEMİ")

    # Klasör oluştur
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if len(root_urls) == 1:
        page_name = unquote(root_urls[0].split('/')[-1])
        page_name = guvenli_dosya_adi(page_name, 25)
    else:
        page_name = f"{len(root_urls)}_sayfa"
    output_folder = f"Scraping_{page_name}_{timestamp}_depth{max_depth}"
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    original_dir = os.getcwd()
    os.chdir(output_folder)
    
    # İnit
    ziyaret_edilenler = set()
    kuyruk = [(url, 0) for url in root_urls]
    tum_sonuclar = []
    json_dosyalar = []
    entity_analyzer = EntityFrequencyAnalyzer()

    # Ayarları göster
    logger.info(f"Root URL sayısı: {len(root_urls)}")
    for i, url in enumerate(root_urls, 1):
        logger.info(f"  [{i}] {url}")
    logger.info(f"Maksimum Derinlik: {max_depth}")
    logger.info(f"Bekleme Süresi: {bekleme_suresi}s")
    logger.info(f"Paralel Worker: {paralel_worker}")
    logger.info(f"Çıktı Klasörü: {output_folder}")
    
    baslangic_zamani = time.time()
    logger.section(f"⏰ İŞLEM BAŞLADI - {datetime.now().strftime('%H:%M:%S')}")
    
    toplam_islenen_sayfa = 0
    derinlik_bazli_sayaclar = {}
    
    # Derinlik bazlı işleme
    # Derinlik bazlı işleme
    for current_depth in range(max_depth + 1):
        if not kuyruk:
            break
        
        # Derinlik istatistiğini başlat
        if current_depth not in derinlik_stats:
            derinlik_stats[current_depth] = {
                'basarili': 0, 
                'basarisiz': 0, 
                'skip': 0, 
                'unique_pairs': 0, 
                'sure': 0,
                'baslangic': time.time()
            }
        else:
            derinlik_stats[current_depth]['baslangic'] = time.time()
        
        # Mevcut derinlik URL'lerini topla
        current_depth_urls = []
        remaining_queue = []
        
        for url, depth in kuyruk:
            if depth == current_depth:
                if (url and isinstance(url, str) and 
                    url.startswith("http") and
                    'action=edit' not in url and 
                    'redlink=1' not in url and
                    '/w/index.php?' not in url and
                    url not in ziyaret_edilenler):
                    current_depth_urls.append((url, depth))
            else:
                remaining_queue.append((url, depth))
        
        kuyruk = remaining_queue
        
        if not current_depth_urls:
            continue
        
        derinlik_bazli_sayaclar[current_depth] = len(current_depth_urls)
        
        # Derinlik başlangıcı
        logger.section(f"🌌 DERİNLİK {current_depth} BAŞLIYOR", char="─", width=80)
        logger.info(f"Bu derinlikte işlenecek: {len(current_depth_urls)} sayfa")
        logger.info(f"Kuyrukta bekleyen: {len(remaining_queue)} sayfa")
        logger.info(f"Şimdiye kadar işlenen: {toplam_islenen_sayfa} sayfa")
        
        derinlik_baslangic = time.time()
        islenen_sayfa_bu_derinlik = 0
        basarili_sayfa = 0
        basarisiz_sayfa = 0
        
        # Paralel işleme
        with ThreadPoolExecutor(max_workers=paralel_worker) as executor:
            future_to_url = {}
            for url_tuple in current_depth_urls:
                future = executor.submit(
                    tek_sayfa_isle, 
                    url_tuple, 
                    entity_analyzer, 
                    ziyaret_edilenler,
                    bekleme_suresi
                )
                future_to_url[future] = url_tuple
            
            for future in as_completed(future_to_url):
                url_tuple = future_to_url[future]
                islenen_sayfa_bu_derinlik += 1
                toplam_islenen_sayfa += 1
                
                progress_pct = (islenen_sayfa_bu_derinlik / len(current_depth_urls)) * 100
                
                # Progress özeti
                logger.subsection(
                    f"İLERLEME: {islenen_sayfa_bu_derinlik}/{len(current_depth_urls)} "
                    f"({progress_pct:.1f}%) | Toplam: {toplam_islenen_sayfa}",
                    indent=0
                )
                
                try:
                    result = future.result()
                    if result:
                        basarili_sayfa += 1
                        json_dosyalar.append(result['json_dosya'])
                        tum_sonuclar.append(result['df'])
                        
                        if result['derinlik'] + 1 <= max_depth:
                            yeni_eklenen = 0
                            for yeni_url in result['yeni_linkler']:
                                if yeni_url not in ziyaret_edilenler:
                                    kuyruk.append((yeni_url, result['derinlik'] + 1))
                                    yeni_eklenen += 1
                            
                            if yeni_eklenen > 0:
                                logger.info(f"➕ {yeni_eklenen} URL kuyruğa eklendi (Toplam: {len(kuyruk)})")
                    else:
                        basarisiz_sayfa += 1
                        
                except Exception as e:
                    basarisiz_sayfa += 1
                    logger.error(f"İş tamamlama hatası", details=str(e)[:100])
        
        # Derinlik özeti
        derinlik_suresi = time.time() - derinlik_baslangic
        dakika, saniye = divmod(int(derinlik_suresi), 60)
        
        # Derinlik süresini kaydet
        derinlik_stats[current_depth]['sure'] = derinlik_suresi
        
        logger.section(f"✅ DERİNLİK {current_depth} TAMAMLANDI", char="─", width=80)
        logger.success(f"Süre: {dakika}:{saniye:02d}")
        logger.success(f"Başarılı: {basarili_sayfa}")
        logger.error(f"Başarısız: {basarisiz_sayfa}")
        
        # Skip edilen sayfa sayısını göster
        skip_count = derinlik_stats[current_depth]['skip']
        if skip_count > 0:
            logger.warning(f"Skip edilen: {skip_count}")
        
        # Unique entity-URL çifti sayısını göster
        unique_pairs = derinlik_stats[current_depth]['unique_pairs']
        logger.info(f"Unique Entity-URL Çifti: {unique_pairs}")
        
        logger.info(f"Sonraki derinlik kuyruğu: {len(kuyruk)}")
        
        # Hata özeti
        if basarisiz_sayfa > 0:
            logger.warning(f"Hata Dağılımı: Network={hata_sayaci['network']}, "
                         f"Parse={hata_sayaci['parse']}, File={hata_sayaci['file']}, "
                         f"Diğer={hata_sayaci['other']}")
    
    # Final raporlar
    if tum_sonuclar:
        logger.section("📊 RAPORLAR OLUŞTURULUYOR")
        ana_df = pd.concat(tum_sonuclar, ignore_index=True)
        ana_df.to_csv("E_U_Toplam.csv", index=False, encoding="utf-8-sig")
        logger.success(f"{len(ana_df)} kayıt 'E_U_Toplam.csv' dosyasında")
        
        e_u_total_cikti("E_U_URL_Bazli_Global_Toplam_Cümleler_Dahil.csv")
    
    if json_dosyalar:
        entity_df, pair_df = entity_analyzer.save_reports(
            entity_report_file="KUMÜLATIF_Entity_Frekanslari.csv",
            pair_report_file="KUMÜLATIF_Entity_URL_Ciftleri.csv",
            min_frequency=2
        )
        
        if entity_df is not None and not entity_df.empty:
            logger.section("🔥 EN SIK GEÇEN 20 ENTİTY")
            top_entities = entity_analyzer.get_top_entities(20)
            print(top_entities[["Entity", "Sayfa_Frekans", "Kaynak_Sayfa_Sayisi"]].to_string(index=False))
    
    # Toplam süre
    toplam_sure = time.time() - baslangic_zamani
    dakika, saniye = divmod(int(toplam_sure), 60)
    saat, dakika = divmod(dakika, 60)
    
    os.chdir(original_dir)
    
    # Final rapor
    logger.section("🎉 İŞLEM TAMAMLANDI!")
    logger.info(f"Toplam Süre: {saat}:{dakika:02d}:{saniye:02d}")
    logger.info(f"Toplam Sayfa: {len(ziyaret_edilenler)}")
    logger.info(f"Ortalama: {len(ziyaret_edilenler)/(toplam_sure/60):.1f} sayfa/dakika")
    logger.info(f"Klasör: {os.path.abspath(output_folder)}")
    
    # Detaylı derinlik raporu
    logger.section("📊 DERİNLİK BAZLI DETAYLI RAPOR", char="=", width=80)
    
    for depth in sorted(derinlik_stats.keys()):
        stats = derinlik_stats[depth]
        toplam_deneme = stats['basarili'] + stats['basarisiz'] + stats['skip']
        
        logger.subsection(f"Derinlik {depth}", indent=0)
        
        # Sayfa istatistikleri
        logger.info(f"├─ Başarılı Scrap: {stats['basarili']}", indent=1)
        logger.error(f"├─ Başarısız Scrap: {stats['basarisiz']}", indent=1)
        logger.warning(f"├─ Skip Edilen: {stats['skip']}", indent=1)
        logger.info(f"├─ Toplam Deneme: {toplam_deneme}", indent=1)
        
        # Entity-URL çifti
        logger.success(f"├─ Unique Entity-URL Çifti: {stats['unique_pairs']}", indent=1)
        
        # Süre
        dk, sn = divmod(int(stats['sure']), 60)
        logger.info(f"└─ Tamamlanma Süresi: {dk}:{sn:02d}", indent=1)
        
        # Başarı oranı
        if toplam_deneme > 0:
            basari_orani = (stats['basarili'] / toplam_deneme) * 100
            logger.progress(f"   Başarı Oranı: %{basari_orani:.1f}", indent=1)
        
        print()  # Boş satır
    
    # Toplam özet
    logger.subsection("GENEL ÖZET")
    toplam_basarili = sum(s['basarili'] for s in derinlik_stats.values())
    toplam_basarisiz = sum(s['basarisiz'] for s in derinlik_stats.values())
    toplam_skip = sum(s['skip'] for s in derinlik_stats.values())
    toplam_unique_pairs = sum(s['unique_pairs'] for s in derinlik_stats.values())
    
    logger.success(f"Toplam Başarılı: {toplam_basarili}")
    logger.error(f"Toplam Başarısız: {toplam_basarisiz}")
    logger.warning(f"Toplam Skip: {toplam_skip}")
    logger.info(f"Toplam Unique Entity-URL Çifti: {toplam_unique_pairs}")
    
    # CSV raporu oluştur
    depth_report = []
    for depth in sorted(derinlik_stats.keys()):
        stats = derinlik_stats[depth]
        dk, sn = divmod(int(stats['sure']), 60)
        depth_report.append({
            'Derinlik': depth,
            'Başarılı': stats['basarili'],
            'Başarısız': stats['basarisiz'],
            'Skip': stats['skip'],
            'Entity-URL_Çifti': stats['unique_pairs'],
            'Süre_Dakika': dk,
            'Süre_Saniye': sn
        })
    
    if depth_report:
        depth_df = pd.DataFrame(depth_report)
        depth_csv = os.path.join(output_folder, "Derinlik_Bazli_İstatistikler.csv")
        depth_df.to_csv(depth_csv, index=False, encoding="utf-8-sig")
        logger.success(f"Derinlik raporu kaydedildi: Derinlik_Bazli_İstatistikler.csv")
    
    logger.subsection("DERİNLİK İSTATİSTİKLERİ")
    for depth, count in sorted(derinlik_bazli_sayaclar.items()):
        logger.info(f"Derinlik {depth}: {count} sayfa")


if __name__ == "__main__":
    logger.section("🎯 WIKIPEDIA ENTITY FREKANS ANALİZ SİSTEMİ")

    # URL listesi txt dosyasından oku
    txt_dosya = input("📄 URL listesi içeren .txt dosyasının adını girin (örn: urls.txt): ").strip()

    if not os.path.exists(txt_dosya):
        logger.error(f"Dosya bulunamadı: {txt_dosya}")
        sys.exit(1)

    urls = []
    with open(txt_dosya, "r", encoding="utf-8") as f:
        for satir in f:
            url = satir.strip()
            if not url or url.startswith("#"):  # Boş satır ve yorum satırlarını atla
                continue
            if "wikipedia.org" in url and url.startswith("http"):
                urls.append(url)
                logger.success(f"Eklendi: {url}")
            else:
                logger.error(f"Geçersiz URL atlandı: {url}")

    if not urls:
        logger.error("Dosyadan geçerli URL okunamadı!")
        sys.exit(1)

    logger.info(f"Toplam {len(urls)} URL yüklendi.")

    while True:
        try:
            depth = int(input("🔢 Maksimum derinlik (0-5 önerilir): ").strip())
            if 0 <= depth <= 10:
                break
            logger.error("Derinlik 0-10 arasında olmalı!")
        except ValueError:
            logger.error("Geçerli bir sayı girin!")

    while True:
        try:
            worker_input = input(f"🚀 Paralel worker (1-{Paralel_worker_max_limit}, default 4): ").strip()
            workers = int(worker_input) if worker_input else 4
            if 1 <= workers <= Paralel_worker_max_limit:
                break
            logger.error(f"Worker sayısı 1-{Paralel_worker_max_limit} arasında olmalı!")
        except ValueError:
            logger.error("Geçerli bir sayı girin!")

    logger.info(f"URL Sayısı: {len(urls)}")
    for i, u in enumerate(urls, 1):
        logger.info(f"  [{i}] {u}")
    logger.info(f"Derinlik: {depth}")
    logger.info(f"Workers: {workers}")

    input("\n⏳ Devam etmek için Enter'a basın...")

    # İşlendi dosyasını kontrol et
    islendi_dosya = "islendi.txt"
    islenen_urls = set()

    if os.path.exists(islendi_dosya):
        with open(islendi_dosya, "r", encoding="utf-8") as f:
            islenen_urls = set(line.strip() for line in f if line.strip())
        logger.warning(f"⏭ Daha önce işlenmiş {len(islenen_urls)} URL atlanacak.")

    for i, url in enumerate(urls, 1):
        if url in islenen_urls:
            logger.warning(f"⏭ [{i}/{len(urls)}] Zaten işlendi, atlanıyor: {url}")
            continue

        logger.section(f"🔗 URL {i}/{len(urls)} İŞLENİYOR: {url}")
        
        try:
            derin_scrap([url], max_depth=depth, bekleme_suresi=1, paralel_worker=workers)
            
            # Başarıyla tamamlandıysa işlendi.txt'ye ekle
            with open(islendi_dosya, "a", encoding="utf-8") as f:
                f.write(url + "\n")
            
            logger.success(f"✅ [{i}/{len(urls)}] Tamamlandı ve işlendi.txt'ye kaydedildi: {url}")
        
        except Exception as e:
            logger.error(f"❌ [{i}/{len(urls)}] Hata oluştu, işlendi.txt'ye eklenmedi: {url}", details=str(e))
            logger.warning("⚠ Bir sonraki URL'ye geçiliyor...")
            continue