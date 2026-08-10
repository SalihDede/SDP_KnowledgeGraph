"""
Türkçe Wikipedia Paragraf Veri Seti Oluşturucu (Dump Tabanlı)
----------------------------------------------------------------
KG (Bilgi Grafiği) triple çıkarımı ve RAG benchmark'ı için paragraf verisi toplar.

Önceki scraping tabanlı yaklaşımın (requests + BeautifulSoup ile tr.wikipedia.org'u
tek tek gezmek) yerine, Hugging Face'te barındırılan resmi Wikipedia dump snapshot'ını
kullanır. Bu yöntemin farkları:

  - Network isteği / 429 rate-limit riski YOK -> saatler değil dakikalar sürer.
  - Metin zaten mwparserfromhell ile temizlenmiş geliyor (infobox, dipnot,
    kaynakça gibi HTML gürültüsü BeautifulSoup'a göre çok daha az).
  - 150.000 sayfadan Türkçe Wikipedia'nın TAMAMINA (şu an ~690k+ madde) kadar
    ölçeklenebilir, sadece max_articles parametresini değiştirmeniz yeterli.

Kurulum:
    pip install datasets

Notlar:
  - Varsayılan config "20231101.tr" (Kasım 2023 snapshot). Daha güncel bir tarih
    eklenmiş mi diye https://huggingface.co/datasets/wikimedia/wikipedia sayfasından
    kontrol edip HF_CONFIG değişkenini güncelleyebilirsiniz. Güncellik kritikse
    (yakın zamanda açılmış maddeler dahil olsun istiyorsanız) resmi
    dumps.wikimedia.org/trwiki dump'ını + wikiextractor/mwparserfromhell ile
    kendiniz işlemeniz gerekir; bu script HF snapshot'ını kullanıyor.
  - Çıktı JSONL (satır başına bir JSON objesi) formatındadır. Milyonlarca paragraf
    için tek bir dev JSON array'ini belleğe yükleyip yazmak yerine, satır satır
    akış (streaming) halinde yazmak çok daha güvenli ve düşük bellek kullanır.
    İstediğiniz orijinal format (tek JSON array) için en alttaki
    convert_jsonl_to_json() fonksiyonunu kullanabilirsiniz.

Bu ortamda (sandbox) huggingface.co'ya network erişimi kapalı olduğu için script
burada TEST EDİLEMEDİ, sadece sözdizimi (syntax) kontrolünden geçirildi. Kendi
ortamınızda (internet erişimi olan) çalıştırmanız gerekiyor.
"""

import json
import re
from typing import List, Optional

from datasets import load_dataset

HF_CONFIG = "20231101.tr"


def clean_paragraph_text(text: str) -> str:
    """Paragraf metnindeki referans/dipnot işaretlerini ve fazla boşlukları temizler."""
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\[kaynak belirtilmeli\]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_article_into_paragraphs(article_text: str, min_words: int = 5) -> List[str]:
    """
    Makale metnini paragraflara böler. HF dataset'indeki 'text' alanı satır
    sonlarıyla ayrılmış paragraflar (ve bazen tek satırlık bölüm başlıkları)
    içerir. min_words'ten az kelimeli satırlar (bölüm başlıkları, artık
    kalıntılar vb.) otomatik elenir -- orijinal scraping kodundaki
    `len(text.split()) > 5` filtresiyle aynı mantık.
    """
    raw_chunks = re.split(r"\n+", article_text)
    paragraphs = []
    for chunk in raw_chunks:
        cleaned = clean_paragraph_text(chunk)
        if len(cleaned.split()) > min_words:
            paragraphs.append(cleaned)
    return paragraphs


def build_benchmark_dataset(
    output_filename: str = "paragraph_dataset.jsonl",
    hf_config: str = HF_CONFIG,
    max_articles: Optional[int] = 150_000,
    min_words: int = 5,
    log_every: int = 5_000,
    shuffle_seed: Optional[int] = 42,
) -> None:
    """
    Ana orkestrasyon fonksiyonu. Wikipedia dump'ından (HF dataset) makaleleri
    okur, paragraflara böler ve JSONL olarak diske yazar.

    max_articles=None verirseniz Türkçe Wikipedia'nın TAMAMI işlenir.
    shuffle_seed=None verirseniz makaleler dataset'teki orijinal sırayla
    (rastgelelik olmadan) işlenir.
    """
    print(f"[BİLGİ] '{hf_config}' Wikipedia dump snapshot'ı yükleniyor "
          f"(ilk çalıştırmada indirilir, sonrasında lokal cache'den okunur)...")
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
                      f"Çıkartılan toplam paragraf: {total_paragraphs}")

    print(f"\n[BAŞARILI] {total_articles} madde işlendi, {total_paragraphs} paragraf "
          f"'{output_filename}' dosyasına yazıldı.")


def convert_jsonl_to_json(jsonl_path: str, json_path: str) -> None:
    """
    JSONL dosyasını orijinal örneğinizdeki formata (tek bir JSON array) çevirir.
    Not: Milyonlarca kayıt için bu işlem hem RAM hem disk açısından pahalıdır;
    yalnızca gerçekten tek bir JSON array dosyası şart ise kullanın. Küçük/orta
    ölçekli alt kümeler (ör. ilk 150k paragraf) için sorunsuzdur.
    """
    records = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"[BAŞARILI] {len(records)} kayıt '{json_path}' dosyasına (JSON array) yazıldı.")


if __name__ == "__main__":
    build_benchmark_dataset(
        output_filename="paragraph_dataset.jsonl",
        hf_config=HF_CONFIG,
        max_articles=None,   # None yaparsanız TÜM Türkçe Wikipedia işlenir (~690k+ madde)
        min_words=5,
        log_every=5_000,
        shuffle_seed=42,
    )

    # Tek JSON array dosyası da istiyorsanız (opsiyonel, dosya boyutuna dikkat edin):
    # convert_jsonl_to_json("paragraph_dataset_150k.jsonl", "paragraph_dataset_150k.json")