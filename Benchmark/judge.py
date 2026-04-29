"""LLM-as-judge for Task 1 (entity) and Task 2 (relation) scoring."""
import os
import time
import requests
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

JUDGE_PROMPT_T1 = """Sen bir bilgi grafiği değerlendirme hakemisin.

Soru tipi: Tail entity prediction (boşluğu doldurma)
Doğru cevap: {truth}
Modelin tahmini: {prediction}

Modelin tahmini, doğru cevabı içeriyor mu? Aşağıdakiler EŞLEŞME sayılır:
- Birebir aynı kelime (Richmond = Richmond)
- Çekimli/eklenmiş hali (mesleği = meslek, Türkiye'de = Türkiye)
- Eş anlamlı veya yakın anlamlı (vatan = ülke, doğum yeri = doğduğu yer)
- Daha spesifik bir form ("Richmond, Virginia" doğru cevap "Richmond" ise eşleşir)
- Tahmin bir liste içinde doğru cevabı barındırıyor

Aşağıdakiler EŞLEŞME SAYILMAZ:
- Tamamen farklı entity (Paris ≠ Londra)
- Aynı kategoriden başka bir değer (futbolcu ≠ basketçi)
- Sadece üst kategori match'i (sporcu, "futbolcu" cevabı için yeterli değil)

Sadece tek kelime cevapla: Evet ya da Hayır."""

JUDGE_PROMPT_T2 = """Sen bir bilgi grafiği değerlendirme hakemisin.

Soru tipi: Relation prediction (iki varlık arasındaki ilişki adı)
Doğru ilişki: {truth}
Modelin tahmini: {prediction}

Modelin tahmini, doğru ilişkiyi içeriyor mu? EŞLEŞME sayılır:
- Birebir aynı (meslek = meslek)
- Çekimli hali (mesleği = meslek)
- Eş anlamlı (uyruk = vatandaşlık ülkesi, doğum yeri = doğduğu yer)
- Liste içinde geçiyorsa (model "meslek, unvan, alan" dediyse ve cevap "meslek")

EŞLEŞME SAYILMAZ:
- Ters yön ilişki (çocuk ≠ ebeveyn, baba ≠ oğul)
- Farklı kategori (doğum yeri ≠ ölüm yeri)
- Çok genel ilişki (model "bağlantı" dedi, doğru cevap "üye olduğu" ise yetersiz)

Sadece tek kelime cevapla: Evet ya da Hayır."""


def llm_judge(prediction: str, truth: str, task: int,
              api_key: str, judge_model: str) -> Dict:
    """Returns {'score': 0/1, 'judge_response': str, 'latency_s': float}."""
    template = JUDGE_PROMPT_T1 if task == 1 else JUDGE_PROMPT_T2
    prompt = template.format(prediction=prediction, truth=truth)

    t0 = time.time()
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={
            "model": judge_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 5,
            "temperature": 0,
        },
        timeout=30,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip().lower()

    score = 1 if "evet" in content or "yes" in content else 0
    return {
        "score": score,
        "judge_response": content,
        "latency_s": round(time.time() - t0, 3),
    }