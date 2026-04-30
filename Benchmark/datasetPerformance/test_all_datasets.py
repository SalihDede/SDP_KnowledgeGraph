"""
3 Test Seti için Tüm Evaluasyonları Çalıştır
"""

import subprocess
import sys
from pathlib import Path

DATASETS = [
    "Wikipediatest.json",
    "KG-Gentest.json",
    "PromptOpttest.json",
]

def run_evaluation(dataset: str, sample_size: int = None, workers: int = 5):
    """Run evaluator for a single dataset."""
    dataset_path = Path(__file__).parent / dataset

    if not dataset_path.exists():
        print(f"[ERROR] Dataset bulunamadı: {dataset_path}")
        return False

    print(f"\n{'='*70}")
    print(f"BAŞLANIYOR: {dataset}")
    print(f"{'='*70}")

    cmd = [
        sys.executable,
        str(Path(__file__).parent / "evaluator.py"),
        "--dataset", str(dataset_path),
        "--workers", str(workers),
    ]

    if sample_size:
        cmd.extend(["--sample", str(sample_size)])

    try:
        result = subprocess.run(cmd, check=True)
        print(f"\n[SUCCESS] {dataset} tamamlandı")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] {dataset} hatası: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test All Datasets")
    parser.add_argument("--sample", type=int, default=None, help="Sample size per dataset")
    parser.add_argument("--workers", type=int, default=5, help="Number of workers")
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"TÜM TEST SETLERİ DEĞERLENDIRMESI")
    print(f"{'='*70}")
    print(f"Sample size: {args.sample or 'Tümü'}")
    print(f"Workers: {args.workers}")
    print(f"{'='*70}\n")

    results = {}
    for dataset in DATASETS:
        success = run_evaluation(dataset, sample_size=args.sample, workers=args.workers)
        results[dataset] = "✓ SUCCESS" if success else "✗ FAILED"

    # Özet
    print(f"\n{'='*70}")
    print(f"ÖZET")
    print(f"{'='*70}")
    for dataset, status in results.items():
        print(f"{dataset:25} : {status}")
    print(f"{'='*70}\n")

    all_success = all(s == "✓ SUCCESS" for s in results.values())
    sys.exit(0 if all_success else 1)
