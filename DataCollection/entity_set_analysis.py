import pandas as pd
import glob

# CSV klasör yolunu belirt
path = "./data"  # örn: "data/"
files = glob.glob(path + "/*.csv")

# Her dosya için entity set'lerini topla
entity_sets = {}
for file in files:
    df = pd.read_csv(file)
    entities = set(df['E'].astype(str))
    entity_sets[file.split('/')[-1]] = entities

# Tüm entity'lerin birleşimini al
all_entities = sorted(set.union(*entity_sets.values()))

# Entity - Dosya varlık matrisi oluştur
presence = pd.DataFrame(0, index=all_entities, columns=entity_sets.keys())
for f, ents in entity_sets.items():
    presence.loc[list(ents), f] = 1

# Ortak entity'leri bul
multi_common = presence[presence.sum(axis=1) > 1]  # birden fazla dosyada geçenler
unique_only = presence[presence.sum(axis=1) == 1]  # sadece bir dosyada geçenler

# Konsola yazdır
print("\n===== 🔁 Ortak (birden fazla dosyada geçen) entity'ler =====")
for entity, row in multi_common.iterrows():
    in_files = list(row[row == 1].index)
    print(f"{entity} → {', '.join(in_files)}")

print("\n===== 🧩 Benzersiz (sadece bir dosyada olan) entity'ler =====")
for entity, row in unique_only.iterrows():
    in_files = list(row[row == 1].index)
    print(f"{entity} → {', '.join(in_files)}")

# İstersen CSV olarak da kaydedebilirsin
multi_common.to_csv("ortak_entityler.csv", encoding="utf-8")
unique_only.to_csv("benzersiz_entityler.csv", encoding="utf-8")
