#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import pandas as pd
from collections import defaultdict

def create_recursive_tree_from_csv(csv_path, cikti_md_adi="recursive_entity_tree.md"):
    """
    CSV'deki tüm entity–parent ilişkilerini (Kaynak_IDler'e göre) okuyup
    çok seviyeli, frekans sıralı bir ağaç yapısı oluşturur.
    """

    df = pd.read_csv(csv_path)

    if df.empty:
        print("⚠️ CSV dosyası boş.")
        return None

    # --- Parent -> [(child, freq)] ilişkisini oluştur ---
    tree = defaultdict(list)
    entity_freq = {}

    for _, row in df.iterrows():
        e = str(row["E"]).strip()
        freq = int(row["Frekans"])
        kaynak = str(row["Kaynak_IDler"]).strip()

        # 🔹 Kaynak_IDler içindeki ilk root'u al (örnek: Kerem Bürsin#1=Kerem BürsinCard#1 → Kerem Bürsin)
        if "=" in kaynak:
            first = kaynak.split("=")[0]  # ilk segment
        else:
            first = kaynak

        parent = first.split("#")[0].replace("Card", "").strip()

        # parent → child ilişkisini kaydet
        if parent and e:
            tree[parent].append((e, freq))
            entity_freq[e] = freq

    # --- Çocuk olan tüm entity’leri topla ---
    all_children = {c for children in tree.values() for c, _ in children}
    roots = [p for p in tree.keys() if p not in all_children]

    if not roots:
        print("⚠️ Kök bulunamadı, varsayılan olarak ilk parent seçildi.")
        roots = [list(tree.keys())[0]]

    # --- Ağaç yazdırıcı (recursive) ---
    def yazdir(node, level=0, visited=None):
        if visited is None:
            visited = set()
        if node in visited:
            return ""
        visited.add(node)

        indent = "│   " * (level - 1) + ("├── " if level > 0 else "")
        freq_info = f" (Frekans: {entity_freq.get(node, '-')})" if level > 0 else ""
        result = indent + node + freq_info + "\n"

        # Alt dalları frekansa göre sırala
        children = sorted(tree.get(node, []), key=lambda x: x[1], reverse=True)
        for child, _ in children:
            result += yazdir(child, level + 1, visited)
        return result

    # --- Tüm kökleri sırayla yaz ---
    final_tree = ""
    for root in sorted(roots):
        final_tree += yazdir(root)

    # --- Markdown çıktısı ---
    with open(cikti_md_adi, "w", encoding="utf-8") as f:
        f.write("```\n" + final_tree + "```")

    print(f"\n✅ Çok seviyeli ağaç '{cikti_md_adi}' dosyasına kaydedildi.\n")
    print(final_tree)
    return final_tree


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Kullanım: python csv_recursive_tree.py <csv_dosyası>")
        sys.exit(1)

    csv_path = sys.argv[1]
    create_recursive_tree_from_csv(csv_path)
