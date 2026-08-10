"""
Türkçe Wikipedia Paragraf Veri Seti Oluşturucu (Dump ve Filtre Tabanlı)
----------------------------------------------------------------
KG (Bilgi Grafiği) triple çıkarımı ve RAG benchmark'ı için paragraf verisi toplar.

Geliştirmeler:
  - Hugging Face'te barındırılan resmi Wikipedia dump snapshot'ı kullanılır (hızlı & bloksuz).
  - Veriler streaming (akış) ile JSONL formatında yazılır (OOM engellenir).
  - Tablo artıkları, şablon parametreleri, HTML tagleri ve İngilizce 
    wiki kalıntıları sezgisel (heuristic) filtrelerle elenir.
  - "Kaynakça", "Dış bağlantılar" gibi alt başlıklara gelindiğinde makale 
    okuması kesilerek (truncation) RAG vektör uzayının kirlenmesi engellenir.

Kurulum:
    pip install datasets
"""

import json
import re
from typing import List, Optional

from datasets import load_dataset

HF_CONFIG = "20231101.tr"


def is_valid_paragraph(text: str, min_words: int = 5) -> bool:
    """
    Paragrafın bilgi grafiği ve RAG için geçerli, anlamlı bir Türkçe metin olup olmadığını denetler.
    """
    # 1. Uzunluk kontrolü
    if len(text.split()) <= min_words:
        return False
        
    # 2. Wiki tablo, başlık veya şablon artıkları ile başlıyorsa
    if text.startswith(("|", "!", "{", "}", "==")):
        return False
        
    # 3. HTML / CSS tablo parametreleri barındırıyorsa
    table_artifacts = ["colspan=", "rowspan=", "align=", "style=", "width=", "bgcolor="]
    if any(artifact in text.lower() for artifact in table_artifacts):
        return False
        
    # 4. Parametre atamaları (örnek: "1=2009 Coupe..." veya resim metadata "thumb|200px")
    if re.match(r"^\w+\s*=", text) or re.match(r"^[0-9]+\s*=", text):
        return False
        
    # 5. Sık rastlanan İngilizce Wikipedia kalıntıları
    english_artifacts = ["results at", "external links", "retrieved from", "official website", "references"]
    if any(artifact in text.lower() for artifact in english_artifacts):
        return False
        
    # 6. Noktalama işareti kontrolü (Anlamlı bir cümlenin/paragrafın sonu)
    # Madde imleri veya tamamlanmamış bozuk satırları engeller.
    if not text.endswith((".", "?", "!", '"', "'", "”", "’")):
        return False
        
    return True


def clean_paragraph_text(text: str) -> str:
    """Paragraf metnindeki referans/dipnot işaretlerini ve fazla boşlukları temizler."""
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\[kaynak belirtilmeli\]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_article_into_paragraphs(article_text: str, min_words: int = 5) -> List[str]:
    """
    Makale metnini paragraflara böler. 'Kaynakça', 'Dış bağlantılar' gibi 
    ek bölümlere gelindiğinde makalenin geri kalanını okumayı keser (truncate).
    """
    raw_chunks = re.split(r"\n+", article_text)
    paragraphs = []
    
    # Ansiklopedik içeriğin bittiğini gösteren standart Wikipedia alt başlıkları
    stop_keywords = {
        "kaynakça", 
        "dış bağlantılar", 
        "ayrıca bakınız", 
        "notlar", 
        "referanslar",
        "ilgili bağlantılar",
        "i̇lgili bağlantılar" # Türkçe "i" karakteri varyasyonları için
    }
    
    for chunk in raw_chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
            
        # Makale sonu (Truncation) Kontrolü:
        # Başlığın etrafındaki olası "==" işaretlerini ve boşlukları temizleyip küçük harfe çeviriyoruz.
        cleaned_header = chunk.lower().replace("=", "").strip()
        if cleaned_header in stop_keywords:
            break  # Döngüyü kır, altındaki hiçbir paragrafı/kaynağı işleme!
            
        # 1. Aşama: Ham paragrafın yapısal olarak uygunluğunu denetle
        if not is_valid_paragraph(chunk, min_words):
            continue
            
        # 2. Aşama: Metni temizle
        cleaned = clean_paragraph_text(chunk)
        
        # 3. Aşama: Temizlik sonrası son kontrolü yap (temizlik metni çok kısaltmış olabilir)
        if len(cleaned.split()) > min_words:
            paragraphs.append(cleaned)
            
    return paragraphs


def build_benchmark_dataset(
    output_filename: str = "paragraph_dataset_clean.jsonl",
    hf_config: str = HF_CONFIG,
    max_articles: Optional[int] = 150_000,
    min_words: int = 5,
    log_every: int = 5_000,
    shuffle_seed: Optional[int] = 42,
) -> None:
    """
    Ana orkestrasyon fonksiyonu. Wikipedia dump'ından (HF dataset) makaleleri
    okur, paragraflara böler, filtreler ve JSONL olarak diske yazar.
    """
    print(f"[BİLGİ] '{hf_config}' Wikipedia dump snapshot'ı yükleniyor...")
    ds = load_dataset("wikimedia/wikipedia", hf_config, split="train")
    print(f"[BİLGİ] Snapshot'ta toplam {len(ds)} madde var.")

    if shuffle_seed is not None:
        ds = ds.shuffle(seed=shuffle_seed)

    if max_articles is not None:
        ds = ds.select(range(min(max_articles, len(ds))))

    total_articles = len(ds)
    print(f"[BİLGİ] {total_articles} madde işlenecek. Çıktı: '{output_filename}' (JSONL)\n")

    total_paragraphs = 0
    with open(output_filename, "w", encoding="utf-8") as f:
        for i, example in enumerate(ds):
            paragraphs = split_article_into_paragraphs(example["text"], min_words=min_words)

            for p_num, paragraph_text in enumerate(paragraphs, start=1):
                record = {
                    "wikipedia_page": example["url"],
                    "paragraph_number": p_num,
                    "paragraph_text": paragraph_text,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_paragraphs += 1

            if (i + 1) % log_every == 0 or (i + 1) == total_articles:
                print(f"İşlenen madde: {i + 1}/{total_articles} | "
                      f"Çıkartılan toplam saf paragraf: {total_paragraphs}")

    print(f"\n[BAŞARILI] {total_articles} madde işlendi, {total_paragraphs} saf paragraf "
          f"'{output_filename}' dosyasına yazıldı.")


def convert_jsonl_to_json(jsonl_path: str, json_path: str) -> None:
    """
    JSONL dosyasını tek bir JSON dizisine çevirir. 
    Yalnızca küçük/orta ölçekli setlerde (ör. ilk 150k satır) test amacıyla kullanılması önerilir.
    """
    records = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"[BAŞARILI] {len(records)} kayıt '{json_path}' dosyasına (JSON array) yazıldı.")


if __name__ == "__main__":
    # Tüm Türkçe Wikipedia'yı (filtrelenmiş haliyle) işlemek için max_articles=None yapabilirsiniz.
    build_benchmark_dataset(
        output_filename="paragraph_dataset_clean.jsonl",
        hf_config=HF_CONFIG,
        max_articles=None,
        min_words=20,
        log_every=5_000,
        shuffle_seed=42,
    )