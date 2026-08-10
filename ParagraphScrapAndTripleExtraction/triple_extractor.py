"""
Multi-Model KG Triple Çıkarım Boru Hattı (Tam Korumalı, Metrikli & Canlı İzlemeli)
--------------------------------------------------------------
Model 1: Gemini 2.5 Flash-Lite (Multi-Thread: 10)
Model 2: GPT-OSS-20B Free (Single-Thread: 1)

Özellikler:
- Çökmelere karşı anında diske yazım (flush).
- Kaldığı yerden devam etme (resume) ile API maliyet koruması.
- Token kullanımı, işlem süresi ve 'uç_tipi' dahil detaylı JSON çıktısı.
- Ağ (network) donmalarına karşı 45 saniyelik zaman aşımı (timeout) koruması.
- Terminal üzerinden canlı süreç takibi.
"""

import os
import json
import time
import re
import concurrent.futures
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    raise ValueError("Lütfen .env dosyanızda OPENROUTER_API_KEY tanımlayın.")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Çıkarım Modelleri ve Thread Yapılandırması
MODELS_CONFIG = [
    {
        "name": "google/gemini-2.5-flash-lite",
        "max_workers": 10, 
        "output_file": "triples_gemini.jsonl"
    },
    {
        "name": "openai/gpt-oss-20b:free",
        "max_workers": 1, 
        "output_file": "triples_gpt_oss.jsonl"
    }
]


def extract_json_array(text):
    """LLM çıktısından JSON dizisini güvenli bir şekilde ayıklar."""
    try:
        text = re.sub(r"```json", "", text)
        text = re.sub(r"```", "", text)
        text = text.strip()
        
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        return []
    except Exception:
        return []


def call_llm_with_metrics(prompt, system_prompt, model_name, max_retries=4):
    """API isteklerini yapar, zamanı ölçer ve token kullanımlarını döndürür."""
    start_time = time.time()
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                timeout=45.0  # EKLENTİ: 45 saniyede cevap gelmezse iptal edip tekrar dener
            )
            elapsed_time = round(time.time() - start_time, 2)
            
            input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') and response.usage else 0
            output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else 0
            content = response.choices[0].message.content
            
            return content, input_tokens, output_tokens, elapsed_time
            
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                sleep_time = (2 ** attempt) + 2
                print(f"[{model_name} - Rate Limit] Bekleniyor... {sleep_time} sn")
                time.sleep(sleep_time)
            elif "timeout" in str(e).lower():
                print(f"[{model_name} - Timeout] API yanıt vermedi, tekrar deneniyor... (Deneme {attempt+1}/{max_retries})")
                time.sleep(2)
            else:
                if attempt == max_retries - 1:
                    print(f"[{model_name} - Hata] LLM Çağrısı Başarısız: {e}")
                    elapsed_time = round(time.time() - start_time, 2)
                    return "", 0, 0, elapsed_time
                time.sleep(2)
                
    elapsed_time = round(time.time() - start_time, 2)
    return "", 0, 0, elapsed_time


def pipeline_extract_triples(paragraph_dict, model_name):
    """3 aşamalı çıkarım boru hattını tek bir paragraf için çalıştırır."""
    text = paragraph_dict.get("paragraph_text", "")
    page_url = paragraph_dict.get("wikipedia_page", "")
    p_num = paragraph_dict.get("paragraph_number", 0)
    
    if not text:
        return []

    # EKLENTİ: Hangi paragrafta olduğumuzu terminalde görmek için print
    print(f"[{model_name}] Paragraf {p_num} işleniyor... (3 Aşamalı İstek Başladı)")

    system_prompt = "Sen Türkçe doğal dil işleme ve Bilgi Grafiği uzmanısın. Yalnızca geçerli bir JSON array formatında yanıt ver. Markdown veya ekstra açıklama ekleme."

    # ADIM 1: Entity Çıkarımı
    prompt_1 = f"""Aşağıdaki metinde geçen varlıkları (kişi, yer, organizasyon vb.) çıkar.
Eğer Wikidata ID'sini (QID) biliyorsan ekle, bilmiyorsan null bırak.
Çıktı formatı: [{{"varlık": "Mustafa Kemal Atatürk", "qid": "Q5152", "tip": "Kişi"}}]

Metin: {text}"""
    
    ent_resp, ent_in, ent_out, ent_time = call_llm_with_metrics(prompt_1, system_prompt, model_name)
    entities = extract_json_array(ent_resp)
    if not entities: return []

    # ADIM 2: Relation Çıkarımı
    prompt_2 = f"""Aşağıdaki metinde geçen varlıklar arasındaki potansiyel ilişkileri çıkar.
Eğer Wikidata Property ID'sini (PID) biliyorsan ekle, bilmiyorsan null bırak.
Çıktı formatı: [{{"ilişki": "doğum yeri", "pid": "P19"}}]

Metin: {text}"""
    
    rel_resp, rel_in, rel_out, rel_time = call_llm_with_metrics(prompt_2, system_prompt, model_name)
    relations = extract_json_array(rel_resp)
    if not relations: return []

    # ADIM 3: Eşleştirme (Triples)
    prompt_3 = f"""Aşağıdaki metni, tespit edilen Varlıkları ve İlişkileri kullanarak (Baş, İlişki, Uç) üçlüleri oluştur.
Sadece listelerdeki verileri kullan.
Çıktı formatı:
[
  {{
    "baş": "Mustafa Kemal Atatürk", "baş_qid": "Q5152", "baş_tipi": "Kişi",
    "ilişki": "doğum yeri", "ilişki_pid": "P19",
    "uç": "Selanik", "uç_qid": "Q17151", "uç_tipi": "Yer"
  }}
]

Metin: {text}
Varlıklar: {json.dumps(entities, ensure_ascii=False)}
İlişkiler: {json.dumps(relations, ensure_ascii=False)}"""

    trip_resp, trip_in, trip_out, trip_time = call_llm_with_metrics(prompt_3, system_prompt, model_name)
    triples_raw = extract_json_array(trip_resp)
    
    if not triples_raw: return []

    # O paragraf için harcanan TOPLAM kaynakları hesapla
    total_input = ent_in + rel_in + trip_in
    total_output = ent_out + rel_out + trip_out
    total_time = round(ent_time + rel_time + trip_time, 2)

    formatted_results = []
    for t in triples_raw:
        formatted_results.append({
            "LLM_Modeli": model_name,
            "wikipedia_page": page_url,
            "paragraph_number": p_num,
            "paragraph_text": text,
            "baş": t.get("baş"),
            "baş_qid": t.get("baş_qid"),
            "baş_tipi": t.get("baş_tipi"),
            "ilişki": t.get("ilişki"),
            "ilişki_pid": t.get("ilişki_pid"),
            "uç": t.get("uç"),
            "uç_qid": t.get("uç_qid"),
            "uç_tipi": t.get("uç_tipi"),
            "input_token": total_input,
            "output_token": total_output,
            "time": f"{total_time} seconds"
        })

    return formatted_results


def get_processed_paragraph_ids(output_file):
    """Daha önce işlenmiş paragrafların ID'lerini okur."""
    processed_ids = set()
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    unique_id = f"{data.get('wikipedia_page')}_{data.get('paragraph_number')}"
                    processed_ids.add(unique_id)
                except Exception:
                    pass
    return processed_ids


def run_extraction_for_model(input_file, records, config):
    model_name = config["name"]
    max_workers = config["max_workers"]
    output_file = config["output_file"]
    
    processed_ids = get_processed_paragraph_ids(output_file)
    
    records_to_process = []
    for r in records:
        unique_id = f"{r.get('wikipedia_page')}_{r.get('paragraph_number')}"
        if unique_id not in processed_ids:
            records_to_process.append(r)
            
    print(f"\n[{model_name}] İşlem başlıyor... (Thread Sayısı: {max_workers})")
    print(f"[{model_name}] İşlenmiş: {len(processed_ids)} | İşlenecek: {len(records_to_process)}")
    
    if not records_to_process:
        print(f"[{model_name}] İşlenecek yeni kayıt yok. Sonraki modele geçiliyor.")
        return

    success_count = 0
    total_triples = 0
    
    with open(output_file, "a", encoding="utf-8") as out_f:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_record = {executor.submit(pipeline_extract_triples, record, model_name): record for record in records_to_process}
            
            for future in concurrent.futures.as_completed(future_to_record):
                try:
                    result_list = future.result()
                    if result_list:
                        for item in result_list:
                            out_f.write(json.dumps(item, ensure_ascii=False) + "\n")
                        out_f.flush()
                        success_count += 1
                        total_triples += len(result_list)
                except Exception as exc:
                    print(f"[{model_name} - HATA] Bir thread çöktü: {exc}")

    print(f"[{model_name}] Tamamlandı! Bu oturumda işlenen Paragraf: {success_count}/{len(records_to_process)} | Toplam Triple: {total_triples}")


def main(input_file="paragraph_dataset_clean.jsonl"):
    print("Veri yükleniyor...")
    records = []
    with open(input_file, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            # i >= 50 kısmını kaldırarak tüm dosyayı işleyebilirsiniz.
            if i >= 50: 
                break
            records.append(json.loads(line))
            
    print("-" * 50)

    for config in MODELS_CONFIG:
        run_extraction_for_model(input_file, records, config)

if __name__ == "__main__":
    main()