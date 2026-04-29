"""
LLM Performance Evaluation on Turkish Knowledge Graph Triples

Her triple için 4 ayrı task, her task ayrı bir JSON satırı olarak kaydedilir.
  Task 1 - Tail Entity Prediction   : entity - relation - X
  Task 2 - Relation Prediction      : entity - X - entity
  Task 3 - True Triple Verification : triple doğru mu? (Evet beklenir)
  Task 4 - False Triple Verification: yanlış relation ile, doğru mu? (Hayır beklenir)

Çalıştırma:
  python translated2kTripletsLLMPerformanceTest.py --model "google/gemini-flash-1.5" --sample 100 --workers 3
"""

import json
import os
import re
import random
import time
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Set, Tuple
from dotenv import load_dotenv
import requests

load_dotenv()

SYSTEM_PROMPT = (
    "Bu bir entity - relation - entity formatında genel bilgi grafiğidir.\n"
    "Verilen triple'lardaki boşlukları dünya bilgine dayanarak mantıklı şekilde doldur."
)

KEPLER_FILE = os.path.join(os.path.dirname(__file__),
    "translatedTriplets", "keplerTR", "translated_triples12b_kepler.txt")
CODEX_FILE = os.path.join(os.path.dirname(__file__),
    "translatedTriplets", "codexTR", "typeClearedTranslatedCodexTriplets.txt")

SEPARATOR_RE = re.compile(r'\s*[-–]\s*')

SOURCE_LABEL = {
    "keplerTR": "Kepler",
    "codexTR":  "Codex",
}


# ─── Veri yükleme ─────────────────────────────────────────────────────────────

def parse_triples(file_path: str) -> List[Dict]:
    triples = []
    dir_name = os.path.basename(os.path.dirname(file_path))
    source = SOURCE_LABEL.get(dir_name, dir_name)

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line.startswith('TR:'):
                continue
            parts = SEPARATOR_RE.split(line[3:].strip(), maxsplit=2)
            if len(parts) == 3:
                triples.append({
                    "entity1":  parts[0].strip(),
                    "relation": parts[1].strip(),
                    "entity2":  parts[2].strip(),
                    "source":   source,
                })
    return triples


# ─── LLM çağrısı ──────────────────────────────────────────────────────────────

def call_llm(prompt: str, api_key: str, model: str) -> Dict:
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens": 300,
            "temperature": 0.3,
        },
        timeout=45,
    )
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage", {})
    return {
        "content":          data["choices"][0]["message"]["content"].strip(),
        "input_tokens":     usage.get("prompt_tokens", 0),
        "output_tokens":    usage.get("completion_tokens", 0),
    }


_TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
_STOPWORDS = {
    "bir", "ve", "ile", "bu", "da", "de", "the", "and", "or", "of", "in", "a", "is",
}
# En uzundan kısaya — normalize edilmiş formda Türkçe ekler
_TR_SUFFIXES = (
    "larin", "lerin", "inin", "unun",
    "ndan", "nden",
    "nin", "nun",
    "dan", "den", "tan", "ten",
    "lari", "leri",
    "lar", "ler",
    "da", "de", "ta", "te", "ya", "ye",
    "ini", "unu",
    "ni", "nu",
    "i", "u",
)

def normalize(text: str) -> str:
    return text.strip().translate(_TR_MAP).lower()

def stem_tr(word_norm: str) -> str:
    """Normalize edilmiş Türkçe kelimeden ortak eki soy; en az 3 karakter kalsın."""
    for suf in _TR_SUFFIXES:
        if word_norm.endswith(suf) and len(word_norm) - len(suf) >= 3:
            return word_norm[:-len(suf)]
    return word_norm

def _relation_stems(rel: str) -> set:
    """Relation'ın normalize+stem edilmiş anlamlı kelimelerini döner (Task 4 için)."""
    return {stem_tr(t) for t in normalize(rel).split() if len(stem_tr(t)) >= 3}

_GENERIC_TURKISH = {
    "belediye", "voyvodaligi", "universite", "fakulte", "enstitutu",
    "ilce", "sehir", "kent", "bolge", "okul", "hastane",
    "kulup", "takim", "dernek", "vakif", "merkez", "tesis",
}

def _high_conf_tokens(truth: str) -> list:
    """Return tokens that are NOT generic Turkish administrative words (high-confidence matchers)."""
    tokens = [w.strip('.,;:()[]"\'–—') for w in truth.split()]
    result = []
    for t in tokens:
        n = normalize(t)
        if len(n) < 4:
            result.append(t)
            continue
        root = stem_tr(n)
        if root in _GENERIC_TURKISH or n in _GENERIC_TURKISH:
            continue
        result.append(t)
    return result

def match_in_response(response: str, truth: str) -> bool:
    resp_norm = normalize(response)

    # A) GT varyantı: sondaki belirsizleştirme parantezi ve nokta temizlenmiş
    gt_variants = [truth]
    gt_cleaned = re.sub(r'\s*\([^)]+\)\s*$', '', truth).strip(' .')
    if gt_cleaned and gt_cleaned != truth:
        gt_variants.append(gt_cleaned)

    for gt in gt_variants:
        # 1. Tam eşleşme
        if normalize(gt) in resp_norm:
            return True
        # 2. Virgülle ayrılmış parçalar
        comma_parts = [p.strip() for p in gt.split(',') if p.strip()]
        if len(comma_parts) > 1 and any(normalize(p) in resp_norm for p in comma_parts):
            return True
        # 3. Yüksek güven: benzersiz varlık isimleri (generic ek olmayanlar)
        high_conf = _high_conf_tokens(gt)
        if high_conf and any(normalize(t) in resp_norm for t in high_conf):
            return True
        # 4. Boşlukla ayrılmış önemli kelimeler (≥4 karakter, stopword değil)
        tokens = [w.strip('.,;:()[]"\'–—') for w in gt.split()]
        significant = [t for t in tokens if len(normalize(t)) >= 4 and normalize(t) not in _STOPWORDS]
        if significant and any(normalize(t) in resp_norm for t in significant):
            return True
        # 5. Türkçe morfoloji: token kökünü tam kelime sınırında ara
        for token in tokens:
            token_n = normalize(token)
            if len(token_n) < 4:
                continue
            stem = stem_tr(token_n)
            if stem != token_n and len(stem) >= 3:
                if re.search(r'(?<!\w)' + re.escape(stem) + r'(?!\w)', resp_norm):
                    return True

    return False

def extract_yes_no(response: str) -> str:
    r = normalize(response)
    if "hayır" in r or "hayir" in r or "no" in r:
        return "hayır"
    if "evet" in r or "yes" in r:
        return "evet"
    return "belirsiz"


# ─── 4 Task ───────────────────────────────────────────────────────────────────

def run_task1(t: Dict, api_key: str, model: str) -> Dict:
    task_input = f"{t['entity1']} - {t['relation']} - X"
    prompt = f"{task_input}\nX için olası cevapları ver, virgülle ayır."
    t0 = time.time()
    llm = call_llm(prompt, api_key, model)
    return {
        "task":            1,
        "task_input":      task_input,
        "llm_predictions": llm["content"],
        "ground_truth":    t['entity2'],
        "score":           1 if match_in_response(llm["content"], t['entity2']) else 0,
        "latency_s":       round(time.time() - t0, 3),
        "input_tokens":    llm["input_tokens"],
        "output_tokens":   llm["output_tokens"],
    }

def run_task2(t: Dict, api_key: str, model: str) -> Dict:
    task_input = f"{t['entity1']} - X - {t['entity2']}"
    prompt = (
        f"{task_input}\n"
        "Bu iki varlık arasındaki ilişkinin ADINI bul. "
        "X bir kavram veya özellik türüdür (örn: 'meslek', 'ülke', 'doğduğu yer', 'tür'). "
        "Somut değer değil, ilişki adlarını virgülle ayırarak ver."
    )
    t0 = time.time()
    llm = call_llm(prompt, api_key, model)
    return {
        "task":            2,
        "task_input":      task_input,
        "llm_predictions": llm["content"],
        "ground_truth":    t['relation'],
        "score":           1 if match_in_response(llm["content"], t['relation']) else 0,
        "latency_s":       round(time.time() - t0, 3),
        "input_tokens":    llm["input_tokens"],
        "output_tokens":   llm["output_tokens"],
    }

def run_task3(t: Dict, api_key: str, model: str) -> Dict:
    task_input = f"{t['entity1']} - {t['relation']} - {t['entity2']}"
    prompt = f"{task_input}\nBu triple doğru mu? Sadece 'Evet' veya 'Hayır' yaz."
    t0 = time.time()
    llm = call_llm(prompt, api_key, model)
    answer = extract_yes_no(llm["content"])
    score = 1 if answer == "evet" else (0 if answer == "hayır" else -1)
    return {
        "task":            3,
        "task_input":      task_input,
        "llm_predictions": llm["content"],
        "ground_truth":    "evet",
        "score":           score,
        "latency_s":       round(time.time() - t0, 3),
        "input_tokens":    llm["input_tokens"],
        "output_tokens":   llm["output_tokens"],
    }

def run_task4(t: Dict, all_relations: List[str], api_key: str, model: str) -> Dict:
    real_stems = _relation_stems(t['relation'])
    candidates = [
        r for r in all_relations
        if normalize(r) != normalize(t['relation'])
        and not (_relation_stems(r) & real_stems)  # eş anlamlı relation'ları ele
    ]
    if not candidates:  # tüm adaylar benzer çıkarsa fallback
        candidates = [r for r in all_relations if normalize(r) != normalize(t['relation'])]
    wrong_relation = random.choice(candidates)
    task_input = f"{t['entity1']} - {wrong_relation} - {t['entity2']}"
    prompt = f"{task_input}\nBu triple doğru mu? Sadece 'Evet' veya 'Hayır' yaz."
    t0 = time.time()
    llm = call_llm(prompt, api_key, model)
    answer = extract_yes_no(llm["content"])
    score = 1 if answer == "hayır" else (0 if answer == "evet" else -1)
    return {
        "task":            4,
        "task_input":      task_input,
        "wrong_relation":  wrong_relation,
        "llm_predictions": llm["content"],
        "ground_truth":    "hayır",
        "score":           score,
        "latency_s":       round(time.time() - t0, 3),
        "input_tokens":    llm["input_tokens"],
        "output_tokens":   llm["output_tokens"],
    }


# ─── Konsol çıktısı ───────────────────────────────────────────────────────────

TASK_LABELS = {
    1: "Task 1 (Tail Entity Prediction)",
    2: "Task 2 (Relation Prediction)",
    3: "Task 3 (True Triple Verification)",
    4: "Task 4 (False Triple Verification)",
}

def print_task_result(model: str, triple: Dict, task_res: Dict):
    print()
    print(f"LLM Modeli     : {model}")
    print(f"Veri kaynağı   : {triple['source']}")
    print(f"Veri orijinali : {triple['entity1']} - {triple['relation']} - {triple['entity2']}")
    print(f"{TASK_LABELS[task_res['task']]:16}: {task_res['task_input']}")
    print(f"LLM tahminler  : {task_res['llm_predictions']}")
    print(f"Sonuç          : {task_res['score']}")


# ─── Ana değerlendirme döngüsü ────────────────────────────────────────────────

def run_evaluation(
    model: str = "google/gemini-flash-1.5",
    sample_size: int = None,
    output_file: str = None,
    delay: float = 0.1,
    workers: int = 5,
):
    api_key = os.getenv("OPENROUTHER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTHER_API_KEY bulunamadı. .env dosyasını kontrol edin.")

    print(f"Model: {model}")
    print("Veriler yükleniyor...")

    kepler = parse_triples(KEPLER_FILE)
    codex  = parse_triples(CODEX_FILE)
    all_triples = kepler + codex
    print(f"Kepler: {len(kepler)} | Codex: {len(codex)} | Toplam: {len(all_triples)}")

    if sample_size:
        random.seed(42)
        all_triples = random.sample(all_triples, min(sample_size, len(all_triples)))
        print(f"Örnek: {len(all_triples)} triple")

    all_relations = list({t['relation'] for t in all_triples})

    if output_file is None:
        safe_model = model.replace("/", "_").replace(":", "_")
        output_file = os.path.join(os.path.dirname(__file__), f"results_{safe_model}.jsonl")

    # Kaldığı yerden devam — done: set of (triple_index, task_num)
    done: Set[Tuple[int, int]] = set()
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("type") == "metadata":
                    continue
                done.add((rec['triple_index'], rec['task']))
        print(f"{len(done)} task kaydı bulundu, kaldığı yerden devam...")

    # Her task ayrı bir JSON satırı olarak append edilir
    out_f = open(output_file, 'a', encoding='utf-8')

    # İlk çalıştırmada metadata satırını yaz
    if not done:
        metadata = {
            "type":         "metadata",
            "model":        model,
            "sample_size":  len(all_triples),
            "task4_relation_pool": sorted(all_relations),
            "relation_pool_size": len(all_relations),
        }
        out_f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
        out_f.flush()

    # Özet skorlar ve thread-safe yardımcılar
    scores: Dict[int, List[int]] = {1: [], 2: [], 3: [], 4: []}
    lock = threading.Lock()
    total = len(all_triples)
    completed = [0]

    def process_triple(idx: int, triple: Dict):
        task_funcs = [
            (1, lambda t=triple: run_task1(t, api_key, model)),
            (2, lambda t=triple: run_task2(t, api_key, model)),
            (3, lambda t=triple: run_task3(t, api_key, model)),
            (4, lambda t=triple: run_task4(t, all_relations, api_key, model)),
        ]
        for task_num, task_fn in task_funcs:
            if (idx, task_num) in done:
                continue
            try:
                result = task_fn()
                record = {
                    "model":        model,
                    "source":       triple['source'],
                    "triple_index": idx,
                    "triple":       f"{triple['entity1']} - {triple['relation']} - {triple['entity2']}",
                    **result,
                }
                with lock:
                    print_task_result(model, triple, result)
                    if result['score'] >= 0:
                        scores[task_num].append(result['score'])
                    out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    out_f.flush()
                time.sleep(delay)
            except Exception as e:
                print(f"  [Triple {idx} Task {task_num} HATA]: {e}")

        with lock:
            completed[0] += 1
            print(f"\n[{completed[0]}/{total}] tamamlandı: {triple['entity1']} - {triple['relation']} - {triple['entity2']}")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_triple, idx, triple): idx
            for idx, triple in enumerate(all_triples)
            if not all((idx, t) in done for t in [1, 2, 3, 4])
        }
        for future in as_completed(futures):
            if future.exception():
                print(f"Triple hatası: {future.exception()}")

    out_f.close()

    # ─── Özet rapor ───────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"MODEL   : {model}")
    print(f"Toplam  : {total} triple")
    print(f"{'─'*60}")
    overall = []
    for task_num, task_scores in scores.items():
        if task_scores:
            acc = sum(task_scores) / len(task_scores)
            overall.append(acc)
            print(f"{TASK_LABELS[task_num]}: {acc:.2%}  ({sum(task_scores)}/{len(task_scores)})")
    if overall:
        print(f"\nGenel Ortalama : {sum(overall)/len(overall):.2%}")
    print(f"{'='*60}")
    print(f"Sonuçlar       : {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Turkish KG Triple LLM Evaluation")
    parser.add_argument("--model",  default="google/gemini-flash-1.5")
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--delay",   type=float, default=0.1)
    parser.add_argument("--workers", type=int,   default=5)
    args = parser.parse_args()

    run_evaluation(
        model=args.model,
        sample_size=args.sample,
        output_file=args.output,
        delay=args.delay,
        workers=args.workers,
    )
