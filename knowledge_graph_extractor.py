import json
import requests
from typing import List, Dict, Any
import os
from dotenv import load_dotenv

class KnowledgeGraphExtractor:
    def __init__(self, openrouter_api_key: str, model_name: str = "anthropic/claude-3.5-sonnet"):
        """
        Knowledge Graph Extractor using OpenRouter API
        
        Args:
            openrouter_api_key: OpenRouter API anahtarınız
            model_name: Kullanılacak model (varsayılan: claude-3.5-sonnet)
        """
        self.api_key = openrouter_api_key
        self.model_name = model_name
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # Sistem promptunu yükle
        self.load_system_prompt()
    
    def load_system_prompt(self):
        """Sistem promptunu JSON dosyasından yükler"""
        try:
            with open("DataCollection/syspromptforWikiDATA.json", "r", encoding="utf-8") as f:
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
                    "role": "user",
                    "content": full_prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4000
        }
        
        try:
            print("🔄 API'ye istek gönderiliyor...")
            response = requests.post(self.base_url, headers=headers, json=data)
            response.raise_for_status()
            
            result = response.json()
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


def main():
    """Ana fonksiyon - interaktif kullanım"""
    print("🤖 Knowledge Graph Extractor")
    print("=" * 40)
    
    # API key kontrolü
    api_key = input("🔑 OpenRouter API anahtarınızı girin: ").strip()
    if not api_key:
        print("❌ API anahtarı gerekli!")
        return
    
    # Model seçimi
    model = input("🤖 Model adı (Enter=varsayılan claude-3.5-sonnet): ").strip()
    if not model:
        model = "anthropic/claude-3.5-sonnet"
    
    # Extractor'ı başlat
    extractor = KnowledgeGraphExtractor(api_key, model)
    
    print("\n" + "=" * 40)
    print("📝 Metin analizi başlıyor...")
    
    while True:
        print("\n" + "-" * 40)
        
        # Metin girişi
        print("📄 Analiz edilecek metni girin (çıkmak için 'quit'):")
        text = input().strip()
        
        if text.lower() in ['quit', 'exit', 'çık']:
            print("👋 Görüşürüz!")
            break
        
        if not text:
            print("❌ Boş metin girdiniz!")
            continue
        
        # Frekans girişi
        frequency_input = input("🔢 İstenilen farklı ilişki türü sayısı (Enter=otomatik): ").strip()
        frequency = None
        if frequency_input.isdigit():
            frequency = int(frequency_input)
        
        # Analiz yap
        results = extractor.extract_knowledge_graph(text, frequency)
        
        if results:
            # Sonuçları göster
            print("\n🎯 ÇIKARILAN KNOWLEDGE GRAPH:")
            print(json.dumps(results, ensure_ascii=False, indent=2))
            
            # Analiz et
            extractor.analyze_results(results)
            
            # Kaydetme seçeneği
            save_choice = input("\n💾 Sonuçları dosyaya kaydetmek ister misiniz? (e/h): ").lower()
            if save_choice == 'e':
                filename = input("📁 Dosya adı (örn: results.json): ").strip()
                if not filename:
                    filename = "knowledge_graph_results.json"
                if not filename.endswith('.json'):
                    filename += '.json'
                
                extractor.save_results(results, filename)
        
        # Devam etme seçeneği
        continue_choice = input("\n🔄 Başka bir metin analiz etmek ister misiniz? (e/h): ").lower()
        if continue_choice != 'e':
            print("👋 Görüşürüz!")
            break


if __name__ == "__main__":
    main()