"""Mevcut results_*.jsonl dosyalarını LLM judge ile yeniden skorla.
Sadece Codex source'lu Task 1 ve 2 kayıtları yargılanır.
Kepler kayıtları ve Task 3/4 dokunulmadan dosyada kalır.

Çıktı: results_<model>_judged_<judge>.jsonl
"""
import os
import json
import glob
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from judge import llm_judge

load_dotenv()
BENCHMARK_DIR = os.path.dirname(os.path.abspath(__file__))


def rescore_file(input_path: str, judge_model: str, api_key: str,
                 workers: int = 4):
    safe_judge = judge_model.replace("/", "_").replace(":", "_")
    base = os.path.basename(input_path).replace(".jsonl", "")
    output_path = os.path.join(BENCHMARK_DIR,
                                f"{base}_judged_{safe_judge}.jsonl")

    cache = {}

    with open(input_path, encoding="utf-8") as f:
        records = [json.loads(l) for l in f if l.strip()]

    def process(rec):
        # Metadata ve verification task'larını dokunmadan geçir
        if rec.get("type") == "metadata" or rec.get("task") in (3, 4):
            return rec
        # Kepler kayıtlarını orijinal skoruyla geçir — sadece Codex'i yargıla
        if rec.get("source") != "Codex":
            return rec

        key = (rec["task"], rec["llm_predictions"], rec["ground_truth"])
        if key in cache:
            j = cache[key]
        else:
            j = llm_judge(rec["llm_predictions"], rec["ground_truth"],
                          rec["task"], api_key, judge_model)
            cache[key] = j

        rec["original_score"] = rec["score"]
        rec["score"] = j["score"]
        rec["judge_model"] = judge_model
        rec["judge_response"] = j["judge_response"]
        rec["judge_latency_s"] = j["latency_s"]
        return rec

    out_records = [None] * len(records)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(process, rec): i for i, rec in enumerate(records)}
        done = 0
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                out_records[i] = fut.result()
            except Exception as e:
                print(f"  [Hata] kayıt {i}: {e}")
                out_records[i] = records[i]  # orijinal kaydı koru
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(records)}")

    # Yazma — None satırları atla (defensive)
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in out_records:
            if rec is None:
                continue
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Özet — None'lara karşı korumalı
    judged = [r for r in out_records
              if r is not None
              and r.get("source") == "Codex"
              and r.get("task") in (1, 2)
              and "original_score" in r]
    flips = sum(1 for r in judged if r["original_score"] != r["score"])
    skipped_kepler = sum(1 for r in out_records
                          if r is not None
                          and r.get("source") == "Kepler"
                          and r.get("task") in (1, 2))

    print(f"\n{output_path}")
    print(f"  Judge'a giden Codex Task 1/2: {len(judged)}")
    print(f"  Atlanan Kepler Task 1/2     : {skipped_kepler}")
    print(f"  Değişen skor sayısı         : {flips}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge-model", default="anthropic/claude-haiku-4-5")
    ap.add_argument("--pattern", default="results_*.jsonl")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    api_key = os.getenv("OPENROUTHER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTHER_API_KEY .env dosyasında bulunamadı.")

    files = [f for f in glob.glob(os.path.join(BENCHMARK_DIR, args.pattern))
             if "_judged_" not in f]

    print(f"Judge: {args.judge_model}")
    print(f"Rescore edilecek dosya: {len(files)}")
    for f in files:
        print(f"\n→ {os.path.basename(f)}")
        rescore_file(f, args.judge_model, api_key, args.workers)