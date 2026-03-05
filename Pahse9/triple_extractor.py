import os
import csv
import json
import time
import re
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

# ---- .env'den tüm konfigürasyon ----
API_KEY = os.getenv("OPENROUTHER_API_KEY")
MODEL_NAME = os.getenv("LLM_MODEL_NAME", "google/gemini-2.5-flash-lite")
SYS_PROMPT_PATH = os.getenv("SYS_PROMPT")
SOURCE = os.getenv("SOURCE", "Wikipedia")

if not API_KEY:
    raise ValueError("OPENROUTHER_API_KEY .env dosyasında tanımlı değil!")

client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1"
)


# ---- System Prompt'u .env'deki SYS_PROMPT dosya yolundan oku ----
def load_system_prompt() -> str:
    if not SYS_PROMPT_PATH or not Path(SYS_PROMPT_PATH).exists():
        raise FileNotFoundError(
            f"SYS_PROMPT dosyası bulunamadı: {SYS_PROMPT_PATH}\n"
            f".env dosyasında SYS_PROMPT yolunu kontrol edin."
        )
    with open(SYS_PROMPT_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    local_vars = {}
    exec(content, {}, local_vars)
    if "system_prompt_tr" not in local_vars:
        raise ValueError(f"SYS_PROMPT dosyasında 'system_prompt_tr' değişkeni bulunamadı: {SYS_PROMPT_PATH}")
    return local_vars["system_prompt_tr"]


SYSTEM_PROMPT = load_system_prompt()
print(f"[OK] System prompt yüklendi: {SYS_PROMPT_PATH}")
print(f"[OK] Model: {MODEL_NAME}")
print(f"[OK] Kaynak: {SOURCE}")

DATA_DIR = Path("/home/salih/workSpace/SDP/DataCollection/data")
OUTPUT_DIR = DATA_DIR / "triple_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

LOG_FILE = OUTPUT_DIR / "process_log.txt"
FAILED_LOG = OUTPUT_DIR / "failed_requests.txt"

MAX_WORKERS = 15
_file_lock = threading.Lock()
_log_lock = threading.Lock()


def log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    with _log_lock:
        print(line)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def parse_kaynak_cumleler(kaynak_idler_raw: str) -> list[str]:
    """Kaynak_IDler sütunundaki | ile ayrılmış cümleleri parse et.
    Her cümleden ID kısmını (ör: DNS#41:) ayıklayıp sadece cümle metnini döndür."""
    parcalar = kaynak_idler_raw.split(" | ")
    cumleler = []
    for parca in parcalar:
        parca = parca.strip()
        match = re.match(r"^[A-Za-zÀ-ÿçÇğĞıİöÖşŞüÜ\s\(\)\.]+#\d+:\s*(.+)$", parca)
        if match:
            cumleler.append(match.group(1).strip())
        else:
            cumleler.append(parca)
    return cumleler


def call_llm(entity_name: str, cumleler: list[str]) -> tuple[str | None, int, int]:
    """LLM'e cümleleri gönderip triple JSON'u ve token bilgilerini al.
    Döndürür: (content, prompt_tokens, completion_tokens)"""
    cumleler_text = "\n".join(f"- {c}" for c in cumleler)

    user_prompt = cumleler_text

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
        )
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        return response.choices[0].message.content, prompt_tokens, completion_tokens
    except Exception as e:
        log(f"  API HATA: {e}")
        return None, 0, 0


def extract_json_from_response(raw: str) -> list | None:
    """LLM cevabından JSON listesini parse et."""
    cleaned = re.sub(r"```json\s*", "", raw)
    cleaned = re.sub(r"```\s*", "", cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        return None
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return None


def format_output_entries(raw_triples: list, entity_url: str) -> list:
    """LLM'den gelen triple'ları istenen çıktı formatına dönüştür.

    Çıktı formatı:
    {
        "Kaynak_LLM_Modeli": "google/gemini-2.5-flash-lite",
        "kaynak_source": "Wikipedia",
        "kaynak_url": "(https://tr.wikipedia.org/wiki/...)",
        "metin": "orijinal cümle...",
        "triple": {
            "baş": "...",
            "baş_tipi": "...",
            "ilişki": "...",
            "uç": "...",
            "uç_tipi": "..."
        }
    }
    """
    entries = []
    for t in raw_triples:
        entry = {
            "Kaynak_LLM_Modeli": MODEL_NAME,
            "kaynak_source": SOURCE,
            "kaynak_url": entity_url,
            "metin": t.get("metin", ""),
            "triple": {
                "baş": t.get("baş", ""),
                "baş_tipi": t.get("baş_tipi", ""),
                "ilişki": t.get("ilişki", ""),
                "uç": t.get("uç", ""),
                "uç_tipi": t.get("uç_tipi", ""),
            }
        }
        entries.append(entry)
    return entries


def append_entries_to_json(output_file: Path, new_entries: list):
    """Yeni entry'leri mevcut JSON dosyasına anlık olarak ekle (thread-safe)."""
    with _file_lock:
        if output_file.exists():
            with open(output_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        else:
            existing = []

        existing.extend(new_entries)

        with open(output_file, "w", encoding="utf-8") as out:
            json.dump(existing, out, ensure_ascii=False, indent=2)


def get_processed_entities(output_file: Path) -> set:
    """Daha önce işlenmiş entity URL'lerini döndür (kaldığı yerden devam için)."""
    if not output_file.exists():
        return set()
    with open(output_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {t.get("kaynak_url") for t in data if "kaynak_url" in t}


def _process_single_entity(csv_name: str, output_file: Path, row_idx: int,
                            entity_name: str, entity_url: str, frekans: int,
                            cumleler: list[str]) -> dict:
    """Tek bir entity'yi işle. İstatistik dict döndür."""
    num_cumleler = len(cumleler)
    log(f"  [{row_idx}] Entity: {entity_name} | Frekans: {frekans} | Cümle sayısı: {num_cumleler}")

    start_time = time.time()
    raw_response, prompt_tokens, completion_tokens = call_llm(entity_name, cumleler)
    elapsed = time.time() - start_time

    if raw_response is None:
        with _file_lock:
            with open(FAILED_LOG, "a", encoding="utf-8") as fl:
                fl.write(f"{csv_name} | {entity_name} | API hatası\n")
        return {"success": False, "triples": 0, "cumleler": num_cumleler,
                "prompt_tokens": 0, "completion_tokens": 0, "elapsed": elapsed}

    triples = extract_json_from_response(raw_response)

    if triples is None:
        log(f"  JSON PARSE HATASI: {entity_name}")
        with _file_lock:
            with open(FAILED_LOG, "a", encoding="utf-8") as fl:
                fl.write(f"{csv_name} | {entity_name} | JSON parse hatası | {raw_response[:200]}\n")
        return {"success": False, "triples": 0, "cumleler": num_cumleler,
                "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "elapsed": elapsed}

    formatted_entries = format_output_entries(triples, entity_url)
    append_entries_to_json(output_file, formatted_entries)
    log(f"  -> {entity_name}: {len(formatted_entries)} triple | {prompt_tokens} in / {completion_tokens} out token | {elapsed:.1f}s")
    return {"success": True, "triples": len(formatted_entries), "cumleler": num_cumleler,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "elapsed": elapsed}


def process_csv(csv_path: Path):
    """Tek bir CSV dosyasını paralel olarak işle."""
    csv_name = csv_path.stem
    output_file = OUTPUT_DIR / f"{csv_name}_triples.json"

    log(f"İŞLENİYOR: {csv_name}")

    processed_urls = get_processed_entities(output_file)
    if processed_urls:
        log(f"  Daha önce işlenmiş entity sayısı: {len(processed_urls)} (atlanacak)")

    # CSV'den tüm işlenecek satırları oku
    tasks = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # header

        row_count = 0
        for row in reader:
            if len(row) < 4:
                continue

            entity_name = row[0].strip()
            entity_url = row[1].strip()
            try:
                frekans = int(row[2].strip())
            except ValueError:
                frekans = 1
            kaynak_idler = row[3].strip()

            if not kaynak_idler:
                continue

            row_count += 1

            if entity_url in processed_urls:
                continue

            cumleler = parse_kaynak_cumleler(kaynak_idler)
            if not cumleler:
                continue

            tasks.append((row_count, entity_name, entity_url, frekans, cumleler))

    log(f"  Toplam satır: {row_count} | İşlenecek entity: {len(tasks)}")

    if not tasks:
        log(f"TAMAMLANDI: {csv_name} | İşlenecek yeni entity yok")
        return {"triples": 0, "cumleler": 0, "prompt_tokens": 0, "completion_tokens": 0,
                "success": 0, "fail": 0, "elapsed": 0}

    total_triples = 0
    total_cumleler = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    success_count = 0
    fail_count = 0

    csv_start = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                _process_single_entity, csv_name, output_file,
                row_idx, entity_name, entity_url, frekans, cumleler
            ): entity_name
            for row_idx, entity_name, entity_url, frekans, cumleler in tasks
        }

        for future in as_completed(futures):
            entity_name = futures[future]
            try:
                stats = future.result()
                total_triples += stats["triples"]
                total_cumleler += stats["cumleler"]
                total_prompt_tokens += stats["prompt_tokens"]
                total_completion_tokens += stats["completion_tokens"]
                if stats["success"]:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                log(f"  BEKLENMEYEN HATA ({entity_name}): {e}")

    csv_elapsed = time.time() - csv_start
    log(f"TAMAMLANDI: {csv_name} | İşlenen: {len(tasks)} | Başarılı: {success_count} | Başarısız: {fail_count} | Triple: {total_triples} | Süre: {csv_elapsed:.1f}s")

    return {
        "triples": total_triples, "cumleler": total_cumleler,
        "prompt_tokens": total_prompt_tokens, "completion_tokens": total_completion_tokens,
        "success": success_count, "fail": fail_count, "elapsed": csv_elapsed
    }


def main():
    log("=" * 60)
    log("TRIPLE EXTRACTION BAŞLADI")
    log(f"Model: {MODEL_NAME}")
    log(f"Kaynak: {SOURCE}")
    log(f"System Prompt: {SYS_PROMPT_PATH}")
    log(f"Veri dizini: {DATA_DIR}")
    log(f"Çıktı dizin: {OUTPUT_DIR}")
    log("=" * 60)

    scraping_dirs = sorted(d for d in DATA_DIR.iterdir() if d.is_dir() and d.name.startswith("Scraping_"))
    log(f"Toplam Scraping dizini: {len(scraping_dirs)}")

    STATS_FILE = OUTPUT_DIR / "directory_stats.csv"
    with open(STATS_FILE, "w", encoding="utf-8", newline="") as sf:
        writer = csv.writer(sf)
        writer.writerow(["dizin", "cumle_sayisi", "triple_sayisi", "prompt_tokens", "completion_tokens",
                         "toplam_token", "basarili", "basarisiz", "sure_sn"])

    for dir_idx, scraping_dir in enumerate(scraping_dirs, 1):
        log(f"\n{'='*60}")
        log(f"DİZİN [{dir_idx}/{len(scraping_dirs)}]: {scraping_dir.name}")
        log(f"{'='*60}")

        csv_files = sorted(scraping_dir.glob("E_U_D*.csv"))
        log(f"  CSV dosyası sayısı: {len(csv_files)}")

        dir_stats = {"triples": 0, "cumleler": 0, "prompt_tokens": 0,
                     "completion_tokens": 0, "success": 0, "fail": 0, "elapsed": 0}
        dir_start = time.time()

        for i, csv_path in enumerate(csv_files, 1):
            log(f"\n--- [{i}/{len(csv_files)}] {csv_path.name} ---")
            csv_stats = process_csv(csv_path)
            for k in dir_stats:
                dir_stats[k] += csv_stats[k]

        dir_stats["elapsed"] = time.time() - dir_start
        total_tokens = dir_stats["prompt_tokens"] + dir_stats["completion_tokens"]

        log(f"\n>>> ÖZET [{scraping_dir.name}]")
        log(f"    Cümle: {dir_stats['cumleler']} | Triple: {dir_stats['triples']}")
        log(f"    Token (girdi): {dir_stats['prompt_tokens']} | Token (çıktı): {dir_stats['completion_tokens']} | Toplam: {total_tokens}")
        log(f"    Başarılı: {dir_stats['success']} | Başarısız: {dir_stats['fail']}")
        log(f"    Süre: {dir_stats['elapsed']:.1f}s")

        with open(STATS_FILE, "a", encoding="utf-8", newline="") as sf:
            writer = csv.writer(sf)
            writer.writerow([scraping_dir.name, dir_stats["cumleler"], dir_stats["triples"],
                             dir_stats["prompt_tokens"], dir_stats["completion_tokens"], total_tokens,
                             dir_stats["success"], dir_stats["fail"], f"{dir_stats['elapsed']:.1f}"])

    # Tüm triple'ları birleştir
    log("\n" + "=" * 60)
    log("TÜM TRIPLE'LAR BİRLEŞTİRİLİYOR...")

    all_combined = []
    for json_file in sorted(OUTPUT_DIR.glob("*_triples.json")):
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            all_combined.extend(data)

    combined_output = OUTPUT_DIR / "ALL_TRIPLES_COMBINED.json"
    with open(combined_output, "w", encoding="utf-8") as out:
        json.dump(all_combined, out, ensure_ascii=False, indent=2)

    log(f"BİRLEŞİK DOSYA: {combined_output}")
    log(f"TOPLAM TRİPLE SAYISI: {len(all_combined)}")
    log("SÜREÇ TAMAMLANDI!")


if __name__ == "__main__":
    main()
