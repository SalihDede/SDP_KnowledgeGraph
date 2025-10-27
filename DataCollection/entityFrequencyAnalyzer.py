import json
import re
import pandas as pd
from collections import defaultdict
import os
from typing import Dict, List, Set

class EntityFrequencyAnalyzer:
    def __init__(self):
        # Global entity frekansları - tüm sayfalar boyunca
        self.global_entity_freq = defaultdict(int)
        # Hangi entity'nin hangi sayfalardan geldiğini takip et
        self.entity_sources = defaultdict(set)
        # Sayfa bilgileri
        self.page_info = {}
        # Entity-URL çiftleri için
        self.entity_url_pairs = defaultdict(int)
        self.pair_sources = defaultdict(set)
        
    def extract_entities_from_text(self, text: str) -> List[Dict]:
        """Metinden entity-URL çiftlerini çıkar"""
        if not text:
            return []
        
        pattern = r"___E:(.*?) U:\((https?://[^\)]+)\)___"
        entities = []
        
        for match in re.finditer(pattern, text):
            entity_name = match.group(1).strip()
            entity_url = match.group(2).strip()
            entities.append({
                "name": entity_name,
                "url": entity_url,
                "pair": f"{entity_name}|{entity_url}"
            })
        
        return entities
    
    def analyze_json_file(self, json_file_path: str) -> Dict:
        """Tek JSON dosyasını analiz et"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return {"error": f"JSON okuma hatası: {str(e)}"}
        
        title = data.get("Title", "Bilinmeyen")
        page_id = f"Page_{len(self.page_info) + 1}"
        self.page_info[page_id] = {
            "title": title,
            "file": json_file_path
        }
        
        # Bu sayfada bulunan entity'ler (tekrarsız)
        page_entities = set()
        page_entity_pairs = set()
        
        # Main kısmındaki cümleleri analiz et
        main_data = data.get("Main", [])
        for item in main_data:
            sentence = item.get("sentence", "")
            entities = self.extract_entities_from_text(sentence)
            
            for entity in entities:
                # Entity adını global frekansta say
                entity_name = entity["name"]
                entity_pair = entity["pair"]
                
                # Bu sayfada daha önce görülmemişse say
                if entity_name not in page_entities:
                    self.global_entity_freq[entity_name] += 1
                    self.entity_sources[entity_name].add(page_id)
                    page_entities.add(entity_name)
                
                # Entity-URL çifti kontrolü
                if entity_pair not in page_entity_pairs:
                    self.entity_url_pairs[entity_pair] += 1
                    self.pair_sources[entity_pair].add(page_id)
                    page_entity_pairs.add(entity_pair)
        
        # Card kısmını analiz et
        card_data = data.get("Card", {})
        for key, value in card_data.items():
            if isinstance(value, str):
                entities = self.extract_entities_from_text(value)
                
                for entity in entities:
                    entity_name = entity["name"]
                    entity_pair = entity["pair"]
                    
                    # Bu sayfada daha önce görülmemişse say
                    if entity_name not in page_entities:
                        self.global_entity_freq[entity_name] += 1
                        self.entity_sources[entity_name].add(page_id)
                        page_entities.add(entity_name)
                    
                    # Entity-URL çifti kontrolü
                    if entity_pair not in page_entity_pairs:
                        self.entity_url_pairs[entity_pair] += 1
                        self.pair_sources[entity_pair].add(page_id)
                        page_entity_pairs.add(entity_pair)
        
        return {
            "page_id": page_id,
            "title": title,
            "unique_entities": len(page_entities),
            "unique_pairs": len(page_entity_pairs),
            "entities_found": list(page_entities),
            "pairs_found": list(page_entity_pairs)
        }
    
    def analyze_multiple_files(self, json_files: List[str]) -> List[Dict]:
        """Birden fazla JSON dosyasını analiz et"""
        results = []
        for json_file in json_files:
            if os.path.exists(json_file):
                result = self.analyze_json_file(json_file)
                results.append(result)
                print(f"✅ {json_file} analiz edildi - {result.get('unique_entities', 0)} farklı entity")
            else:
                print(f"❌ Dosya bulunamadı: {json_file}")
        return results
    
    def get_entity_frequency_report(self, min_frequency: int = 2) -> pd.DataFrame:
        """Entity frekans raporunu oluştur"""
        if not self.global_entity_freq:
            print("❌ Henüz analiz edilmiş veri yok!")
            return pd.DataFrame()
        
        # Frekansı min_frequency'den büyük olan entity'leri al
        filtered_entities = {
            entity: freq for entity, freq 
            in self.global_entity_freq.items() 
            if freq >= min_frequency
        }
        
        report_data = []
        for entity_name, frequency in filtered_entities.items():
            # Bu entity'nin hangi sayfalardan geldiğini bul
            source_pages = list(self.entity_sources[entity_name])
            source_titles = [
                self.page_info[page_id]["title"] 
                for page_id in source_pages 
                if page_id in self.page_info
            ]
            
            report_data.append({
                "Entity": entity_name,
                "Sayfa_Frekans": frequency,
                "Kaynak_Sayfa_Sayisi": len(source_pages),
                "Kaynak_Basliklar": " | ".join(source_titles),
                "Sayfa_IDleri": " | ".join(source_pages)
            })
        
        df = pd.DataFrame(report_data)
        if not df.empty:
            df = df.sort_values("Sayfa_Frekans", ascending=False)
        return df
    
    def get_entity_url_pairs_report(self, min_frequency: int = 2) -> pd.DataFrame:
        """Entity-URL çiftlerinin frekans raporunu oluştur"""
        if not self.entity_url_pairs:
            print("❌ Henüz analiz edilmiş entity-URL çifti yok!")
            return pd.DataFrame()
        
        # Frekansı min_frequency'den büyük olan çiftleri al
        filtered_pairs = {
            pair: freq for pair, freq 
            in self.entity_url_pairs.items() 
            if freq >= min_frequency
        }
        
        report_data = []
        for pair, frequency in filtered_pairs.items():
            # Pair'i ayır
            entity_name, entity_url = pair.split("|", 1)
            
            # Bu çiftin hangi sayfalardan geldiğini bul
            source_pages = list(self.pair_sources[pair])
            source_titles = [
                self.page_info[page_id]["title"] 
                for page_id in source_pages 
                if page_id in self.page_info
            ]
            
            report_data.append({
                "Entity": entity_name,
                "URL": entity_url,
                "Sayfa_Frekans": frequency,
                "Kaynak_Sayfa_Sayisi": len(source_pages),
                "Kaynak_Basliklar": " | ".join(source_titles),
                "Sayfa_IDleri": " | ".join(source_pages)
            })
        
        df = pd.DataFrame(report_data)
        if not df.empty:
            df = df.sort_values("Sayfa_Frekans", ascending=False)
        return df
    
    def save_reports(self, 
                    entity_report_file: str = "Entity_Frekanslari.csv",
                    pair_report_file: str = "Entity_URL_Ciftleri_Frekanslari.csv",
                    min_frequency: int = 2):
        """Raporları CSV olarak kaydet"""
        
        # Entity frekans raporu
        entity_df = self.get_entity_frequency_report(min_frequency)
        if not entity_df.empty:
            entity_df.to_csv(entity_report_file, index=False, encoding='utf-8-sig')
            print(f"📊 Entity frekans raporu kaydedildi: {entity_report_file}")
            print(f"📈 Toplam {len(entity_df)} entity (min frekans: {min_frequency})")
        
        # Entity-URL çifti raporu
        pair_df = self.get_entity_url_pairs_report(min_frequency)
        if not pair_df.empty:
            pair_df.to_csv(pair_report_file, index=False, encoding='utf-8-sig')
            print(f"📊 Entity-URL çift raporu kaydedildi: {pair_report_file}")
            print(f"📈 Toplam {len(pair_df)} çift (min frekans: {min_frequency})")
        
        return entity_df, pair_df
    
    def search_entity(self, entity_name: str) -> Dict:
        """Belirli bir entity'nin detaylarını ara"""
        entity_name = entity_name.strip()
        
        # Büyük/küçük harf duyarsız arama
        matching_entities = [e for e in self.global_entity_freq.keys() 
                           if entity_name.lower() in e.lower()]
        
        if not matching_entities:
            return {"error": f"'{entity_name}' benzeri entity bulunamadı!"}
        
        results = []
        for entity in matching_entities:
            frequency = self.global_entity_freq[entity]
            source_pages = list(self.entity_sources[entity])
            source_info = []
            
            for page_id in source_pages:
                if page_id in self.page_info:
                    source_info.append({
                        "page_id": page_id,
                        "title": self.page_info[page_id]["title"],
                        "file": self.page_info[page_id]["file"]
                    })
            
            results.append({
                "entity": entity,
                "sayfa_frekans": frequency,
                "sayfa_sayisi": len(source_pages),
                "kaynak_sayfalar": source_info
            })
        
        return {"bulunan_entityler": results}
    
    def get_top_entities(self, n: int = 20) -> pd.DataFrame:
        """En sık geçen N entity'yi getir"""
        df = self.get_entity_frequency_report(min_frequency=1)
        return df.head(n) if not df.empty else pd.DataFrame()

def main():
    """Test ve örnek kullanım"""
    analyzer = EntityFrequencyAnalyzer()
    
    # Mevcut JSON dosyalarını bul
    json_files = [f for f in os.listdir('.') if f.endswith('.json') and f.startswith('Wiki_')]
    
    if json_files:
        print(f"🔍 {len(json_files)} JSON dosyası bulundu: {json_files}")
        results = analyzer.analyze_multiple_files(json_files)
        
        # Raporları oluştur
        print("\n📊 Entity frekans raporları oluşturuluyor...")
        entity_df, pair_df = analyzer.save_reports(min_frequency=2)
        
        if entity_df is not None and not entity_df.empty:
            print("\n🔥 En sık geçen 15 entity:")
            top_entities = analyzer.get_top_entities(15)
            print(top_entities[["Entity", "Sayfa_Frekans", "Kaynak_Sayfa_Sayisi"]].to_string(index=False))
        
        # Özet bilgi
        total_unique_entities = len(analyzer.global_entity_freq)
        total_pages = len(analyzer.page_info)
        print(f"\n📈 ÖZET İSTATİSTİKLER:")
        print(f"   • Toplam farklı entity: {total_unique_entities}")
        print(f"   • Analiz edilen sayfa: {total_pages}")
        
    else:
        print("❌ JSON dosyası bulunamadı! Önce scraping yapmalısınız.")

if __name__ == "__main__":
    main()