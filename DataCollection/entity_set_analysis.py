import pandas as pd
import glob
import os
from collections import defaultdict
from upsetplot import UpSet, from_memberships
import matplotlib.pyplot as plt

# === 1️⃣ CSV klasör yolunu belirt ===
path = "./data"
if not os.path.exists(path):
    raise FileNotFoundError(f"Klasör bulunamadı: {path}")

files = glob.glob(os.path.join(path, "*.csv"))
if not files:
    raise FileNotFoundError(f"{path} klasöründe hiç CSV dosyası bulunamadı.")

# === 2️⃣ Her dosyadaki entity setlerini oluştur ===
entity_sets = {}
for file in files:
    try:
        df = pd.read_csv(file)
        if 'E' not in df.columns:
            print(f"⚠️ {os.path.basename(file)} dosyasında 'E' sütunu yok, atlandı.")
            continue

        df = df.dropna(subset=['E'])
        df['E'] = df['E'].astype(str)
        entities = set(df['E'])
        entity_sets[os.path.basename(file)] = entities

        print(f"✅ {os.path.basename(file)} okundu, {len(entities)} entity bulundu.")
    except Exception as e:
        print(f"❌ {file} okunamadı: {e}")

if len(entity_sets) < 2:
    raise ValueError("Grafik oluşturmak için en az 2 CSV dosyası gerekli.")

# === 3️⃣ Her entity’nin hangi dosyalarda bulunduğunu belirle ===
entity_to_files = defaultdict(list)
for fname, ents in entity_sets.items():
    for e in ents:
        entity_to_files[e].append(fname)

# === 4️⃣ UpSet verisi oluştur ===
memberships = [tuple(v) for v in entity_to_files.values()]
data = from_memberships(memberships)

# === 5️⃣ UpSet grafiğini çiz ===
plt.figure(figsize=(10, 6))
upset = UpSet(
    data,
    subset_size='count',
    show_counts='%d',
    sort_by='cardinality',
    sort_categories_by=None,
)
upset.plot()
plt.suptitle("CSV Dosyalarındaki Entity Kesişimleri — UpSet Plot", fontsize=14)
plt.savefig("entity_upset_plot.png", dpi=300, bbox_inches='tight')
plt.show()

print("\n💾 'entity_upset_plot.png' kaydedildi — çok kümeli entity kesişimleri görselleştirildi.")
