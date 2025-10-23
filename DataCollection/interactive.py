import pandas as pd
import glob
import os
from collections import defaultdict
import plotly.express as px

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

# === 4️⃣ Kesişim kombinasyonlarını ve entity listelerini oluştur ===
intersection_data = defaultdict(list)
for entity, file_list in entity_to_files.items():
    key = tuple(sorted(file_list))
    intersection_data[key].append(entity)

records = []
for combo, ents in intersection_data.items():
    records.append({
        "Kesişim": " ∩ ".join(combo),
        "Dosya Sayısı": len(combo),
        "Entity Sayısı": len(ents),
        "Entityler": ", ".join(ents[:20]) + ("..." if len(ents) > 20 else "")
    })

df_plot = pd.DataFrame(records)
df_plot = df_plot.sort_values("Entity Sayısı", ascending=False)

# === 5️⃣ Interaktif Plotly grafiği ===
fig = px.bar(
    df_plot,
    x="Kesişim",
    y="Entity Sayısı",
    hover_data={"Entityler": True, "Dosya Sayısı": True},
    title="CSV Dosyalarındaki Entity Kesişimleri (Interaktif UpSet Görünümü)",
    labels={"Entity Sayısı": "Ortak Entity Sayısı", "Kesişim": "Dosya Kombinasyonu"},
    color="Dosya Sayısı",
    color_continuous_scale="Viridis"
)

fig.update_layout(
    template="plotly_white",
    xaxis_tickangle=-30,
    hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial"),
)

# === 6️⃣ Kaydet ve göster ===
fig.write_html("entity_interactive_upset.html")
fig.show()

print("\n💾 'entity_interactive_upset.html' kaydedildi — fareyle kesişimlerin üzerine gelerek entity’leri görebilirsin.")
