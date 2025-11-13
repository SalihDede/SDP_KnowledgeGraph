import json
import requests
import pandas as pd
from typing import List, Dict, Any
import os
from dotenv import load_dotenv

class KnowledgeGraphExtractor:
    def __init__(self, openrouter_api_key: str = None, model_name: str = "anthropic/claude-3.7-sonnet:thinking"):
        """
        Knowledge Graph Extractor using OpenRouter API
        
        Args:
            openrouter_api_key: OpenRouter API anahtarınız (None ise .env'den yükler)
            model_name: Kullanılacak model (varsayılan: meta-llama/llama-3.2-3b-instruct:free)
        """
        # .env dosyasını yükle
        load_dotenv()
        
        # API key'i al
        if openrouter_api_key:
            self.api_key = openrouter_api_key
        else:
            self.api_key = os.getenv("openrouter_api_key")
            if not self.api_key:
                raise ValueError("OpenRouter API key bulunamadı! .env dosyasına 'openrouter_api_key' ekleyin.")
        
        self.model_name = model_name
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # Sistem promptunu yükle
        self.load_system_prompt()
    
    def load_system_prompt(self):
        """Sistem promptunu JSON dosyasından yükler"""
        try:
            # Dosya yolunu düzelt
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            prompt_file = os.path.join(parent_dir, "syspromptforWikiDATA.json")
            
            with open(prompt_file, "r", encoding="utf-8") as f:
                content = f.read()
                
            # JSON içeriğini Python kodu olarak çalıştır
            exec(content, globals())
            
            # Global değişkenleri al
            self.examples = globals().get('örnekler', [])
            self.system_prompt = globals().get('system_prompt_tr', '')
            
            print("✅ Sistem promptu başarıyla yüklendi")
            print(f"📝 {len(self.examples)} örnek yüklendi")
            
        except Exception as e:
            print(f"❌ Sistem promptu yüklenirken hata: {e}")
            self.examples = []
            self.system_prompt = ""
    
    def extract_knowledge_graph(self, text: str, frequency: int = None) -> List[Dict[str, Any]]:
        """
        Metinden knowledge graph çıkarır
        
        Args:
            text: Analiz edilecek metin
            frequency: İstenilen farklı ilişki türü sayısı
            
        Returns:
            Knowledge graph triple'ları listesi
        """
        
        # Frekans bilgisini prompta ekle
        frequency_instruction = ""
        if frequency:
            frequency_instruction = f"\n\n**ÖNEMLİ**: Bu metinden tam olarak {frequency} farklı ilişki türü çıkarmalısın."
        
        # Örnek formatı hazırla
        examples_text = "\n\n## Örnek Çıktı Formatı:\n"
        examples_text += json.dumps(self.examples[:3], ensure_ascii=False, indent=2)
        
        # Tam prompt hazırla
        full_prompt = f"""
{self.system_prompt}

{examples_text}

{frequency_instruction}

## Analiz Edilecek Metin:
{text}

Lütfen yukarıdaki metni analiz ederek knowledge graph triple'larını JSON formatında çıkar. Sadece JSON listesini döndür, başka açıklama ekleme.
"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user", 
                    "content": f"Aşağıdaki metni analiz ederek knowledge graph triple'larını JSON formatında çıkar:\n\n{text}\n\nSadece JSON listesini döndür."
                }
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
            "stream": False
        }
        
        try:
            print("🔄 API'ye istek gönderiliyor...")
            response = requests.post(self.base_url, headers=headers, json=data, timeout=30)
            
            # Debugging için response status ve content'i kontrol et
            print(f"📊 HTTP Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ API Hatası: {response.status_code}")
                print(f"📄 Hata detayı: {response.text}")
                return []
            
            result = response.json()
            
            if 'choices' not in result or not result['choices']:
                print("❌ API yanıtında 'choices' bulunamadı")
                print(f"📄 Tam yanıt: {result}")
                return []
                
            content = result['choices'][0]['message']['content']
            
            # JSON çıktısını parse et
            try:
                # Eğer content markdown kod bloğu içindeyse temizle
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                knowledge_graph = json.loads(content.strip())
                
                print(f"✅ {len(knowledge_graph)} triple çıkarıldı")
                return knowledge_graph
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON parse hatası: {e}")
                print(f"📄 Ham çıktı: {content}")
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"❌ API hatası: {e}")
            return []
    
    def save_results(self, results: List[Dict[str, Any]], filename: str):
        """Sonuçları JSON dosyasına kaydet"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"✅ Sonuçlar {filename} dosyasına kaydedildi")
        except Exception as e:
            print(f"❌ Kaydetme hatası: {e}")
    
    def save_clean_output(self, results: List[Dict[str, Any]], base_filename: str):
        """Sonuçları sadece temel 6 alanla temiz formatta kaydet"""
        try:
            # Dosya adını hazırla
            name_without_ext = base_filename.replace('.json', '').replace('.csv', '')
            
            # Sadece temel triple bilgileri (temiz format)
            clean_results = []
            for result in results:
                clean_triple = {
                    "metin": result.get('metin', ''),
                    "baş": result.get('baş', ''),
                    "baş_tipi": result.get('baş_tipi', ''), 
                    "ilişki": result.get('ilişki', ''),
                    "uç": result.get('uç', ''),
                    "uç_tipi": result.get('uç_tipi', '')
                }
                clean_results.append(clean_triple)
            
            output_file = f"{name_without_ext}_knowledge_graph.json"
            self.save_results(clean_results, output_file)
            
            print(f"🎯 Temiz formatta çıktı dosyası oluşturuldu:")
            print(f"   📄 {output_file}")
            
        except Exception as e:
            print(f"❌ Clean output kaydetme hatası: {e}")
    
    def analyze_results(self, results: List[Dict[str, Any]]):
        """Çıkarılan triple'ları analiz et"""
        if not results:
            print("❌ Analiz edilecek sonuç bulunamadı")
            return
        
        # İstatistikleri hesapla
        relations = [item.get('ilişki', '') for item in results]
        entity_types = []
        
        for item in results:
            entity_types.extend([item.get('baş_tipi', ''), item.get('uç_tipi', '')])
        
        unique_relations = set(relations)
        unique_entity_types = set(entity_types)
        
        print("\n📊 ANALIZ SONUÇLARI:")
        print(f"🔗 Toplam triple sayısı: {len(results)}")
        print(f"🔀 Farklı ilişki türü sayısı: {len(unique_relations)}")
        print(f"🏷️ Farklı varlık türü sayısı: {len(unique_entity_types)}")
        
        print(f"\n🔀 İlişki türleri: {', '.join(sorted(unique_relations))}")
        print(f"🏷️ Varlık türleri: {', '.join(sorted(unique_entity_types))}")
    
    def process_csv_file(self, csv_file_path: str) -> List[Dict[str, Any]]:
        """
        CSV dosyasından metinleri okuyup knowledge graph çıkarır
        Her entity'nin kendi frekans değeri CSV'den otomatik olarak okunur
        
        Args:
            csv_file_path: CSV dosyasının yolu
            
        Returns:
            Tüm metinlerden çıkarılan knowledge graph triple'ları
        """
        try:
            # CSV dosyasını oku
            df = pd.read_csv(csv_file_path)
            print(f"📄 CSV dosyası yüklendi: {len(df)} satır")
            
            all_results = []
            
            # Her satırdaki metinleri işle
            total_entities = len(df)
            processed_entities = 0
            
            for index, row in df.iterrows():
                entity = row['E']
                url = row['U'] 
                freq = row['Frekans']
                texts = row['Kaynak_IDler']
                
                processed_entities += 1
                print(f"\n🔄 [{processed_entities}/{total_entities}] İşleniyor: {entity} (Frekans: {freq})")
                
                # Metinleri ayır (| karakteri ile ayrılmış)
                text_parts = texts.split(' | ')
                
                for i, text_part in enumerate(text_parts):
                    if text_part.strip():
                        # Her metin parçasını ayrı ayrı işle
                        print(f"  📝 Metin {i+1}/{len(text_parts)}...", end=" ")
                        
                        # Knowledge graph çıkar - CSV'den gelen gerçek frekans değerini kullan
                        results = self.extract_knowledge_graph(text_part.strip(), freq)
                        
                        # Her sonuca orijinal metin ekle
                        for result in results:
                            result['metin'] = text_part.strip()
                        
                        all_results.extend(results)
                        print(f"✓ {len(results)} triple")
                        
                        # Rate limiting için bekleme
                        import time
                        time.sleep(2)  # API rate limit için 2 saniye bekle
            
            print(f"\n✅ Toplam {len(all_results)} triple çıkarıldı")
            
            # Temiz formatta kaydet
            self.save_clean_output(all_results, csv_file_path)
            
            return all_results
            
        except Exception as e:
            print(f"❌ CSV işleme hatası: {e}")
            return []
    
    def process_multiple_csv_files(self, csv_folder_path: str, frequency: int = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Bir klasördeki tüm CSV dosyalarını işler
        
        Args:
            csv_folder_path: CSV dosyalarının bulunduğu klasör
            frequency: İstenilen farklı ilişki türü sayısı
            
        Returns:
            Her dosya için çıkarılan knowledge graph'lar
        """
        import glob
        
        csv_files = glob.glob(os.path.join(csv_folder_path, "*.csv"))
        print(f"📁 Bulunan CSV dosya sayısı: {len(csv_files)}")
        
        all_file_results = {}
        
        for csv_file in csv_files:
            file_name = os.path.basename(csv_file)
            print(f"\n📄 İşleniyor: {file_name}")
            
            results = self.process_csv_file(csv_file, frequency)
            all_file_results[file_name] = results
            
            # Her dosya sonrası sonuçları kaydet
            output_file = csv_file.replace('.csv', '_knowledge_graph.json')
            self.save_results(results, output_file)
        
        return all_file_results


def main():
    """Hızlı CSV İşleyici - Sadece CSV yolu ister"""
    print("🚀 Hızlı Knowledge Graph Extractor")
    print("=" * 40)
    
    try:
        # Extractor'ı başlat (sabit model ile)
        extractor = KnowledgeGraphExtractor()
        print("✅ Sistem hazır - Model: meta-llama/llama-3.2-3b-instruct:free")
    except ValueError as e:
        print(f"❌ {e}")
        return
    
    # Sadece CSV dosya yolu al
    csv_file = input("\n📁 CSV dosyasının tam yolunu girin: ").strip()
    if not os.path.exists(csv_file):
        print("❌ Dosya bulunamadı!")
        return
    
    print(f"📄 CSV dosyası: {csv_file}")
    print("🔄 İşleme başlıyor... (CSV'den frekans değerleri otomatik okunuyor)")
    
    # CSV'yi işle (frekans değerleri CSV'den otomatik okunuyor)
    results = extractor.process_csv_file(csv_file)
    
    if results:
        # Analiz et
        extractor.analyze_results(results)
        print("\n🎉 İşlem tamamlandı!")
    else:
        print("❌ Hiç sonuç çıkarılamadı")


if __name__ == "__main__":
    main()