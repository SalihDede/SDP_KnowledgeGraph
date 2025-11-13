##############################################################################
## Girdi Formatı Örneği:
##   { *.json dosyalarıında bulunan KG triple'ları }
## json yapısı
##   {
##      "baş": "Lamine Yamal",
##       "baş_tipi": "Kişi",
##       "ilişki": "Kazandı",
##       "uç": "La Liga 2022-23 Sezonu",
##       "uç_tipi": "Turnuva"
##   },
## Çıktı formatından interaktif bir karşılaştırma grafiği ve detaylı analizler sunar
## Çalıştırmak için:     streamlit run json_triple_analyzer.py
##############################################################################
import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from itertools import combinations
from pathlib import Path
import os
from rapidfuzz import fuzz, process
from collections import defaultdict
import re

# Graf görselleştirme kütüphaneleri kaldırıldı - sadece tablo görünümü kullanılıyor

class TripleAnalyzer:
    """JSON dosyalarındaki KG triple'ları analiz eden sınıf"""
    
    def __init__(self):
        self.data = {}
        self.triple_sets = {}
        self.entity_clusters = {}
        self.similar_entities = {}
        
    def load_json_files(self, folder_path):
        """Klasördeki JSON dosyalarını yükler"""
        folder = Path(folder_path)
        self.data = {}
        
        for json_file in folder.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.data[json_file.stem] = data
                    st.success(f"✅ {json_file.stem}.json dosyası yüklendi ({len(data)} triple)")
            except Exception as e:
                st.error(f"❌ {json_file.stem}.json dosyası yüklenirken hata: {str(e)}")
        
        return len(self.data) > 0
    
    def load_merged_files(self, folder_path):
        """mergedformOfAboveTriples klasöründeki dosyaları yükler"""
        merged_folder = Path(folder_path) / "mergedformOfAboveTriples"
        self.merged_data = {}
        
        if not merged_folder.exists():
            st.warning("⚠️ mergedformOfAboveTriples klasörü bulunamadı!")
            return False
        
        merged_files = [
            "entity_types_merged.json",
            "relations_merged.json", 
            "relations_and_types_merged.json",
            "statistics.json"
        ]
        
        loaded_count = 0
        for filename in merged_files:
            file_path = merged_folder / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.merged_data[filename.replace('.json', '')] = data
                        loaded_count += 1
                        if filename != "statistics.json":
                            st.success(f"✅ {filename} yüklendi ({len(data)} kayıt)")
                        else:
                            st.success(f"✅ {filename} yüklendi")
                except Exception as e:
                    st.error(f"❌ {filename} yüklenirken hata: {str(e)}")
            else:
                st.warning(f"⚠️ {filename} bulunamadı!")
        
        return loaded_count > 0
    
    def create_triple_sets(self):
        """Her dosya için triple setleri oluşturur"""
        self.triple_sets = {}
        
        for file_name, triples in self.data.items():
            triple_set = set()
            for triple in triples:
                # Tuple olarak (baş, ilişki, uç) formatında sakla
                triple_tuple = (
                    triple.get('baş', ''),
                    triple.get('ilişki', ''),
                    triple.get('uç', '')
                )
                triple_set.add(triple_tuple)
            self.triple_sets[file_name] = triple_set
    
    def calculate_intersections(self):
        """Dosyalar arası kesişimleri hesaplar"""
        file_names = list(self.triple_sets.keys())
        intersections = {}
        
        # Çiftli kesişimler
        for file1, file2 in combinations(file_names, 2):
            intersection = self.triple_sets[file1] & self.triple_sets[file2]
            intersections[f"{file1} ∩ {file2}"] = intersection
        
        # Üçlü kesişim (eğer 3 dosya varsa)
        if len(file_names) == 3:
            triple_intersection = self.triple_sets[file_names[0]] & self.triple_sets[file_names[1]] & self.triple_sets[file_names[2]]
            intersections[f"{file_names[0]} ∩ {file_names[1]} ∩ {file_names[2]}"] = triple_intersection
        
        return intersections
    
    def create_heatmap_data(self):
        """Heatmap için veri matrisini oluşturur"""
        file_names = list(self.triple_sets.keys())
        n = len(file_names)
        matrix = [[0 for _ in range(n)] for _ in range(n)]
        hover_data = [[[] for _ in range(n)] for _ in range(n)]
        
        for i, file1 in enumerate(file_names):
            for j, file2 in enumerate(file_names):
                if i == j:
                    # Diagonal: dosyanın kendisi
                    matrix[i][j] = len(self.triple_sets[file1])
                    hover_data[i][j] = list(self.triple_sets[file1])[:10]  # İlk 10 triple
                else:
                    # Kesişim
                    intersection = self.triple_sets[file1] & self.triple_sets[file2]
                    matrix[i][j] = len(intersection)
                    hover_data[i][j] = list(intersection)
        
        return matrix, hover_data, file_names
    
    def normalize_entity(self, entity):
        """Varlık adını normalize eder"""
        if not entity:
            return ""
        # Küçük harfe çevir, baştaki/sondaki boşlukları temizle
        normalized = entity.strip().lower()
        # Çoklu boşlukları tek boşluğa çevir
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    def find_similar_entities(self, entities, threshold=85):
        """Benzer varlıkları bulur (fuzzy matching ile)"""
        entity_list = list(set(entities))
        clusters = defaultdict(list)
        processed = set()
        
        for entity in entity_list:
            if entity in processed:
                continue
                
            # Bu varlığa benzer olanları bul
            similar = []
            for other_entity in entity_list:
                if other_entity != entity:
                    similarity = fuzz.ratio(
                        self.normalize_entity(entity),
                        self.normalize_entity(other_entity)
                    )
                    if similarity >= threshold:
                        similar.append((other_entity, similarity))
            
            if similar:
                # En uzun/en anlamlı ismi cluster başı yap
                cluster_entities = [entity] + [s[0] for s in similar]
                cluster_head = max(cluster_entities, key=len)
                clusters[cluster_head] = cluster_entities
                processed.update(cluster_entities)
            else:
                clusters[entity] = [entity]
                processed.add(entity)
        
        return dict(clusters)
    
    def analyze_entity_relationships(self):
        """Benzer varlıklar arasındaki ilişki farklılıklarını analiz eder"""
        all_entities = set()
        entity_relations = defaultdict(lambda: defaultdict(set))
        
        # Tüm varlıkları topla ve ilişkilerini kaydet
        for file_name, triples in self.data.items():
            for triple in triples:
                bas = triple.get('baş', '')
                iliski = triple.get('ilişki', '')
                uc = triple.get('uç', '')
                
                all_entities.add(bas)
                all_entities.add(uc)
                
                # Her varlık çifti için ilişkileri kaydet
                entity_pair = tuple(sorted([bas, uc]))
                entity_relations[entity_pair][iliski].add(file_name)
        
        # Benzer varlıkları bul
        self.entity_clusters = self.find_similar_entities(all_entities)
        
        # Cluster'lar arası ilişki farklılıklarını analiz et
        relationship_analysis = []
        
        for cluster_head, cluster_entities in self.entity_clusters.items():
            if len(cluster_entities) > 1:
                # Bu cluster'daki varlıkları içeren tüm ilişkileri bul
                cluster_relations = defaultdict(lambda: defaultdict(set))
                
                for entity_pair, relations in entity_relations.items():
                    entity1, entity2 = entity_pair
                    
                    # Her iki varlık da bu cluster'da mı?
                    cluster1 = None
                    cluster2 = None
                    
                    for head, entities in self.entity_clusters.items():
                        if entity1 in entities:
                            cluster1 = head
                        if entity2 in entities:
                            cluster2 = head
                    
                    if cluster1 == cluster_head or cluster2 == cluster_head:
                        target_entity = entity2 if cluster1 == cluster_head else entity1
                        
                        for relation, files in relations.items():
                            cluster_relations[target_entity][relation].update(files)
                
                # Aynı hedef varlık için farklı ilişkiler var mı?
                for target_entity, relations in cluster_relations.items():
                    if len(relations) > 1:
                        relationship_analysis.append({
                            'cluster_head': cluster_head,
                            'cluster_entities': cluster_entities,
                            'target_entity': target_entity,
                            'relations': dict(relations),
                            'relation_count': len(relations)
                        })
        
        return relationship_analysis
    
    def analyze_merged_data_quality(self):
        """Merged data kalitesini analiz eder"""
        if not hasattr(self, 'merged_data') or not self.merged_data:
            return None
        
        analysis = {}
        
        # Statistics analizi
        if 'statistics' in self.merged_data:
            stats = self.merged_data['statistics']
            analysis['reduction_efficiency'] = {
                'original_records': stats.get('original_records', 0),
                'entity_types_reduction': stats.get('unique_entities', 0),
                'relations_reduction': stats.get('merged_relations', 0),
                'relations_types_reduction': stats.get('merged_relations_with_types', 0)
            }
            
            # Verimlilik yüzdeleri
            original = stats.get('original_records', 1)
            analysis['efficiency_percentages'] = {
                'entity_types_efficiency': round((1 - stats.get('unique_entities', 0) / original) * 100, 2),
                'relations_efficiency': round((1 - stats.get('merged_relations', 0) / original) * 100, 2),
                'relations_types_efficiency': round((1 - stats.get('merged_relations_with_types', 0) / original) * 100, 2)
            }
        
        # Entity types analizi
        if 'entity_types_merged' in self.merged_data:
            entity_data = self.merged_data['entity_types_merged']
            entity_type_distribution = defaultdict(int)
            multi_type_entities = []
            
            for entity_record in entity_data:
                entity_types = entity_record.get('entity_type', '').split(', ')
                for ent_type in entity_types:
                    if ent_type.strip():
                        entity_type_distribution[ent_type.strip()] += 1
                
                if len(entity_types) > 1:
                    multi_type_entities.append({
                        'entity': entity_record.get('entity', ''),
                        'types': entity_types,
                        'type_count': len(entity_types)
                    })
            
            analysis['entity_analysis'] = {
                'type_distribution': dict(entity_type_distribution),
                'multi_type_entities': multi_type_entities,
                'total_entities': len(entity_data)
            }
        
        # Relations analizi
        if 'relations_merged' in self.merged_data:
            relations_data = self.merged_data['relations_merged']
            relation_distribution = defaultdict(int)
            multi_relation_pairs = []
            
            for relation_record in relations_data:
                relations = relation_record.get('ilişki', '').split(', ')
                for relation in relations:
                    if relation.strip():
                        relation_distribution[relation.strip()] += 1
                
                if len(relations) > 1:
                    multi_relation_pairs.append({
                        'head': relation_record.get('baş', ''),
                        'tail': relation_record.get('uç', ''),
                        'relations': relations,
                        'relation_count': len(relations)
                    })
            
            analysis['relation_analysis'] = {
                'relation_distribution': dict(relation_distribution),
                'multi_relation_pairs': multi_relation_pairs,
                'total_pairs': len(relations_data)
            }
        
        # Relations with types analizi
        if 'relations_and_types_merged' in self.merged_data:
            relations_types_data = self.merged_data['relations_and_types_merged']
            type_combination_stats = defaultdict(int)
            complex_records = []
            
            for record in relations_types_data:
                head_types = record.get('baş_tipi', '').split(', ') if record.get('baş_tipi') else ['N/A']
                tail_types = record.get('uç_tipi', '').split(', ') if record.get('uç_tipi') else ['N/A']
                relations = record.get('ilişki', '').split(', ')
                
                # Tip kombinasyonları
                for h_type in head_types:
                    for t_type in tail_types:
                        type_combination_stats[f"{h_type.strip()} → {t_type.strip()}"] += 1
                
                # Karmaşık kayıtlar (çoklu tip/ilişki)
                complexity_score = len(head_types) + len(tail_types) + len(relations)
                if complexity_score > 5:  # Eşik değeri
                    complex_records.append({
                        'head': record.get('baş', ''),
                        'tail': record.get('uç', ''),
                        'head_types': head_types,
                        'tail_types': tail_types,
                        'relations': relations,
                        'complexity_score': complexity_score
                    })
            
            analysis['relations_types_analysis'] = {
                'type_combinations': dict(type_combination_stats),
                'complex_records': sorted(complex_records, key=lambda x: x['complexity_score'], reverse=True),
                'total_records': len(relations_types_data)
            }
        
        return analysis
    
    def compare_original_vs_merged(self):
        """Orijinal veri ile merged veri arasında karşılaştırma yapar"""
        if not hasattr(self, 'merged_data') or not self.merged_data:
            return None
        
        comparison = {
            'coverage_analysis': {},
            'information_loss': {},
            'data_consistency': {}
        }
        
        # Orijinal verideki unique entity'leri topla
        original_entities = set()
        original_relations = set()
        original_triples = set()
        
        for file_name, triples in self.data.items():
            for triple in triples:
                head = triple.get('baş', '')
                tail = triple.get('uç', '')
                relation = triple.get('ilişki', '')
                
                original_entities.add(head)
                original_entities.add(tail)
                original_relations.add(relation)
                original_triples.add((head, relation, tail))
        
        # Merged verideki entity'leri topla
        merged_entities = set()
        merged_relations = set()
        merged_triples = set()
        
        if 'relations_and_types_merged' in self.merged_data:
            for record in self.merged_data['relations_and_types_merged']:
                head = record.get('baş', '')
                tail = record.get('uç', '')
                relations = record.get('ilişki', '').split(', ')
                
                merged_entities.add(head)
                merged_entities.add(tail)
                for rel in relations:
                    if rel.strip():
                        merged_relations.add(rel.strip())
                        merged_triples.add((head, rel.strip(), tail))
        
        # Coverage analizi
        comparison['coverage_analysis'] = {
            'entity_coverage': len(merged_entities & original_entities) / len(original_entities) * 100 if original_entities else 0,
            'relation_coverage': len(merged_relations & original_relations) / len(original_relations) * 100 if original_relations else 0,
            'triple_coverage': len(merged_triples & original_triples) / len(original_triples) * 100 if original_triples else 0,
            'original_entity_count': len(original_entities),
            'merged_entity_count': len(merged_entities),
            'original_relation_count': len(original_relations),
            'merged_relation_count': len(merged_relations)
        }
        
        # Kayıp entities
        lost_entities = original_entities - merged_entities
        new_entities = merged_entities - original_entities
        
        comparison['information_loss'] = {
            'lost_entities': list(lost_entities)[:20],  # İlk 20'si
            'lost_entity_count': len(lost_entities),
            'new_entities': list(new_entities)[:20],  # İlk 20'si
            'new_entity_count': len(new_entities)
        }
        
        return comparison

def main():
    st.set_page_config(
        page_title="KG Triple Analiz Aracı",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🔍 JSON KG Triple Analiz Aracı")
    st.markdown("---")
    
    # Sidebar
    st.sidebar.header("📁 Dosya Yönetimi")
    
    # Varsayılan klasör yolu
    default_folder = r"c:\Users\Hp\Desktop\SDP\Wikipedia_Wikidata_compare"
    
    folder_path = st.sidebar.text_input(
        "JSON dosyalarının bulunduğu klasör yolu:",
        value=default_folder
    )
    
    analyzer = TripleAnalyzer()
    
    # Merged dosyaları da yükle seçeneği
    load_merged = st.sidebar.checkbox("📊 Merged dosyalarını da yükle", value=True, help="mergedformOfAboveTriples klasöründeki dosyaları da analiz eder")
    
    if st.sidebar.button("📂 Dosyaları Yükle", type="primary"):
        if os.path.exists(folder_path):
            if analyzer.load_json_files(folder_path):
                st.session_state.analyzer = analyzer
                st.session_state.data_loaded = True
                
                # Merged dosyaları da yükle
                if load_merged:
                    if analyzer.load_merged_files(folder_path):
                        st.session_state.merged_loaded = True
                    else:
                        st.session_state.merged_loaded = False
                        st.info("ℹ️ Merged dosyalar yüklenemedi, sadece orijinal dosyalar analiz edilecek.")
                else:
                    st.session_state.merged_loaded = False
            else:
                st.error("Klasörde JSON dosyası bulunamadı!")
        else:
            st.error("Belirtilen klasör bulunamadı!")
    
    # Eğer veri yüklenmişse analizleri göster
    if hasattr(st.session_state, 'data_loaded') and st.session_state.data_loaded:
        analyzer = st.session_state.analyzer
        analyzer.create_triple_sets()
        
        # 1. Dosya Bilgileri
        st.header("📊 Dosya Bilgileri")
        st.info("""
        **🎯 Bu analiz neyi gösterir:** Her JSON dosyasındaki toplam triple (üçlü) sayısını karşılaştırır.
        
        **📖 Nasıl okumalı:** 
        - Yüksek sayı = O dosyada daha fazla bilgi/ilişki var
        - Düşük sayı = Daha az veri içeriyor
        - **Örnek:** LLMWithCasualDataExample: 85 triple → Bu dosyada 85 adet "baş-ilişki-uç" üçlüsü var
        """)
        col1, col2, col3 = st.columns(3)
        
        file_names = list(analyzer.data.keys())
        for i, (file_name, triples) in enumerate(analyzer.data.items()):
            with [col1, col2, col3][i % 3]:
                st.metric(
                    label=f"📄 {file_name}",
                    value=f"{len(triples)} triple"
                )
        
        st.markdown("---")
        
        # 2. Kesişim Analizi (Tam Eşleşme)
        st.header("🔗 Kesişim Analizi (Tam Eşleşme)")
        st.info("""
        **🎯 Bu analiz neyi gösterir:** Dosyalar arasında tamamen aynı olan triple'ları bulur (baş, ilişki, uç değerleri birebir aynı).
        
        **📖 Nasıl okumalı:**
        - Yüksek kesişim = Dosyalar benzer bilgiler içeriyor, tutarlılık var
        - Düşük kesişim = Dosyalar farklı perspektiflerden bilgi içeriyor
        - **Örnek:** "LLM ∩ WikiData: 15 triple" → Bu iki dosyada tamamen aynı olan 15 üçlü var
        - **Örnek Triple:** ("Messi", "Oynadı", "Barcelona") her iki dosyada da aynı şekilde geçiyor
        """)
        
        intersections = analyzer.calculate_intersections()
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📈 Kesişim Sayıları")
            for intersection_name, intersection_set in intersections.items():
                st.metric(
                    label=intersection_name,
                    value=f"{len(intersection_set)} triple"
                )
        
        with col2:
            st.subheader("📋 Kesişim Detayları")
            selected_intersection = st.selectbox(
                "Detaylarını görmek istediğiniz kesişimi seçin:",
                list(intersections.keys())
            )
            
            if selected_intersection:
                intersection_triples = list(intersections[selected_intersection])
                if intersection_triples:
                    df = pd.DataFrame(intersection_triples, columns=['Baş', 'İlişki', 'Uç'])
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("Bu kesişimde triple bulunamadı.")
        
        st.markdown("---")
        
        # 3. Interaktif Heatmap
        st.header("🔥 Interaktif Kesişim Heatmap'i")
        st.info("""
        **🎯 Bu analiz neyi gösterir:** Dosyalar arası kesişimleri görsel matris olarak sunar. Her hücre iki dosya arasındaki ortak triple sayısını gösterir.
        
        **📖 Nasıl okumalı:**
        - **Koyu mavi = Yüksek kesişim** (dosyalar çok benzer)
        - **Açık mavi = Düşük kesişim** (dosyalar farklı)
        - **Diagonal (köşegen)** = Dosyanın kendisi (toplam triple sayısı)
        - **Hover** = Hücrenin üzerine gelin, örnek triple'ları görün
        - **Örnek:** X ekseni "LLM", Y ekseni "WikiData" kesişimi 25 → Bu iki kaynakta 25 ortak triple var
        """)
        
        
        matrix, hover_data, file_names = analyzer.create_heatmap_data()
        
        # Hover text oluştur
        hover_text = []
        for i in range(len(file_names)):
            hover_row = []
            for j in range(len(file_names)):
                triples_preview = hover_data[i][j][:5]  # İlk 5 triple
                preview_text = "<br>".join([f"• {t[0]} → {t[1]} → {t[2]}" for t in triples_preview])
                if len(hover_data[i][j]) > 5:
                    preview_text += f"<br>... ve {len(hover_data[i][j]) - 5} triple daha"
                
                hover_text_cell = f"<b>{file_names[i]} ∩ {file_names[j]}</b><br>"
                hover_text_cell += f"Triple Sayısı: {matrix[i][j]}<br><br>"
                if preview_text:
                    hover_text_cell += f"Örnek Triple'lar:<br>{preview_text}"
                else:
                    hover_text_cell += "Triple bulunamadı"
                
                hover_row.append(hover_text_cell)
            hover_text.append(hover_row)
        
        fig = go.Figure(data=go.Heatmap(
            z=matrix,
            x=file_names,
            y=file_names,
            hovertemplate='%{hovertext}<extra></extra>',
            hovertext=hover_text,
            colorscale='Blues',
            showscale=True,
            colorbar=dict(title="Triple Sayısı")
        ))
        
        fig.update_layout(
            title="Dosyalar Arası Kesişim Haritası",
            xaxis_title="Dosyalar",
            yaxis_title="Dosyalar",
            width=700,
            height=600,
            font=dict(size=12)
        )
        
        # Hücre değerlerini göster
        for i in range(len(file_names)):
            for j in range(len(file_names)):
                fig.add_annotation(
                    x=j,
                    y=i,
                    text=str(matrix[i][j]),
                    showarrow=False,
                    font=dict(color="white" if matrix[i][j] > max(max(row) for row in matrix) * 0.5 else "black", size=14, family="Arial Black")
                )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 4. Detaylı Analiz
        st.markdown("---")
        st.header("🔍 Detaylı Triple Analizi")
        st.info("""
        **🎯 Bu analiz neyi gösterir:** Seçilen dosyanın tüm triple'larını filtrelenebilir tablo olarak sunar.
        
        **📖 Nasıl okumalı:**
        - **Filtreleme** = Belirli varlık/ilişki arayabilirsiniz
        - **Örnek Filtre:** "Baş filtresi: Messi" → Sadece Messi ile başlayan triple'ları gösterir
        - **Örnek Çıktı:** | Messi | Oynadı | Barcelona | → Messi Barcelona'da oynadı
        - **Kullanım:** Spesifik varlık/ilişki hakkında ne bilgi var görmek için
        """)
        
        
        # Seçilen dosyanın triple'larını göster
        selected_file = st.selectbox("Detaylarını görmek istediğiniz dosyayı seçin:", file_names)
        
        if selected_file:
            st.subheader(f"📄 {selected_file} - Triple Listesi")
            triples_list = list(analyzer.triple_sets[selected_file])
            df_detailed = pd.DataFrame(triples_list, columns=['Baş', 'İlişki', 'Uç'])
            
            # Filtreleme seçenekleri
            col1, col2, col3 = st.columns(3)
            with col1:
                bas_filter = st.text_input("Baş filtresi (boş bırakın = hepsi):")
            with col2:
                iliski_filter = st.text_input("İlişki filtresi (boş bırakın = hepsi):")
            with col3:
                uc_filter = st.text_input("Uç filtresi (boş bırakın = hepsi):")
            
            # Filtreleri uygula
            if bas_filter:
                df_detailed = df_detailed[df_detailed['Baş'].str.contains(bas_filter, case=False, na=False)]
            if iliski_filter:
                df_detailed = df_detailed[df_detailed['İlişki'].str.contains(iliski_filter, case=False, na=False)]
            if uc_filter:
                df_detailed = df_detailed[df_detailed['Uç'].str.contains(uc_filter, case=False, na=False)]
            
            st.dataframe(df_detailed, use_container_width=True)
            st.info(f"Toplam {len(df_detailed)} triple gösteriliyor.")
        
        # 5. Benzer Varlık Analizi (Entity Normalization)
        st.markdown("---")
        st.header("🔗 Benzer Varlık Analizi (Entity Normalization)")
        st.info("""
        **🎯 Bu analiz neyi gösterir:** Farklı yazılış şekillerine sahip ama aynı anlama gelen varlıkları bulur ve bunların farklı ilişkilerini karşılaştırır.
        
        **📖 Nasıl okumalı:**
        - **Benzer Varlıklar:** "Lionel Messi", "L. Messi", "Messi" → Aynı kişi, farklı yazılış
        - **Farklı İlişkiler:** Aynı varlığın farklı dosyalarda farklı ilişkileri olabilir
        - **Örnek:** "Messi" bir dosyada "Kazandı" ilişkisiyle, diğerinde "Oynadı" ilişkisiyle geçiyor
        - **Sonuç:** Veri tutarsızlıklarını ve eksik bilgileri tespit eder
        """)
        
        
        with st.spinner("Benzer varlıklar analiz ediliyor..."):
            relationship_analysis = analyzer.analyze_entity_relationships()
        
        if relationship_analysis:
            st.subheader("🎯 Aynı Varlık, Farklı İlişkiler")
            st.info(f"Toplam {len(relationship_analysis)} varlık grubu için farklı ilişkiler tespit edildi.")
            
            # Analiz sonuçlarını göster
            for i, analysis in enumerate(relationship_analysis[:10]):  # İlk 10 sonucu göster
                with st.expander(f"📋 {analysis['cluster_head']} - {analysis['relation_count']} farklı ilişki"):
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        st.write("**Benzer Varlıklar:**")
                        for entity in analysis['cluster_entities']:
                            st.write(f"• {entity}")
                        
                        st.write(f"**Hedef Varlık:** {analysis['target_entity']}")
                    
                    with col2:
                        st.write("**Farklı İlişkiler:**")
                        relations_df = []
                        for relation, files in analysis['relations'].items():
                            relations_df.append({
                                'İlişki': relation,
                                'Dosyalar': ', '.join(files),
                                'Dosya Sayısı': len(files)
                            })
                        
                        df_relations = pd.DataFrame(relations_df)
                        st.dataframe(df_relations, use_container_width=True)
            
            if len(relationship_analysis) > 10:
                st.info(f"... ve {len(relationship_analysis) - 10} grup daha. Tam liste için detaylı analiz bölümünü kullanın.")
        else:
            st.info("Farklı ilişkilere sahip benzer varlık bulunamadı.")
        
        # 6. Merged Data Analysis (Eğer yüklenmişse)
        if hasattr(st.session_state, 'merged_loaded') and st.session_state.merged_loaded:
            st.markdown("---")
            st.header("🔄 Merged Data Detaylı Analizi")
            st.info("""
            **🎯 Bu analiz neyi gösterir:** Merge işlemi sonrası elde edilen temizlenmiş verinin kalitesini ve verimliliğini analiz eder.
            
            **📖 Nasıl okumalı:**
            - **Azaltma %:** Orijinal veriden ne kadar azaltma sağlandı (yüksek = daha verimli temizlik)
            - **Çoklu Tipli Varlıklar:** Birden fazla türü olan varlıklar (zengin içerik)
            - **Karmaşık Kayıtlar:** Çok sayıda ilişki/tip içeren kayıtlar (detaylı bilgi)
            - **Örnek:** %65 azaltma → Orijinal 200 kayıt 70'e düştü, %65 duplicat temizlendi
            """)
            
            

                
            # Orijinal vs Merged karşılaştırması
            st.subheader("⚖️ Orijinal vs Merged Karşılaştırması")
            comparison = analyzer.compare_original_vs_merged()
            
            if comparison:
                # Coverage analizi
                coverage = comparison['coverage_analysis']
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        "Varlık Kapsamı",
                        f"{coverage['entity_coverage']:.1f}%",
                        help="Orijinal varlıkların ne kadarı merged'de korundu"
                    )
                with col2:
                    st.metric(
                        "İlişki Kapsamı",
                        f"{coverage['relation_coverage']:.1f}%"
                    )
                with col3:
                    st.metric(
                        "Triple Kapsamı", 
                        f"{coverage['triple_coverage']:.1f}%"
                    )
                
                # Kayıp/Yeni bilgiler
                info_loss = comparison['information_loss']
                col1, col2 = st.columns(2)
                
                with col1:
                    if info_loss['lost_entities']:
                        st.write(f"**Kayıp Varlıklar ({info_loss['lost_entity_count']} adet):**")
                        for entity in info_loss['lost_entities']:
                            st.write(f"• {entity}")
                    else:
                        st.write("✅ Hiç varlık kaybedilmedi!")
                
                with col2:
                    if info_loss['new_entities']:
                        st.write(f"**Yeni Varlıklar ({info_loss['new_entity_count']} adet):**")
                        for entity in info_loss['new_entities']:
                            st.write(f"• {entity}")
                    else:
                        st.write("ℹ️ Yeni varlık eklenmedi")
                
                # Merged dosya içerikleri - basitleştirilmiş
                st.subheader("📂 Merged Dosya İçerikleri")
                
                # İstatistikler önce
                if 'statistics' in analyzer.merged_data:
                    st.write("**📊 İstatistikler:**")
                    stats = analyzer.merged_data['statistics']
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Orijinal Kayıt", stats.get('original_records', 0))
                    with col2:
                        st.metric("Unique Varlık", stats.get('unique_entities', 0))
                    with col3:
                        st.metric("Merged İlişki", stats.get('merged_relations', 0))
                
                # Basit tablo görünümleri
                if 'entity_types_merged' in analyzer.merged_data:
                    st.write("**📋 Entity Types (Varlık Tipleri):**")
                    entity_df = pd.DataFrame(analyzer.merged_data['entity_types_merged'])
                    st.dataframe(entity_df, use_container_width=True, height=300)

                if 'relations_merged' in analyzer.merged_data:
                    st.write("**🔗 Relations (İlişkiler):**") 
                    relations_df = pd.DataFrame(analyzer.merged_data['relations_merged'])
                    st.dataframe(relations_df, use_container_width=True, height=300)

                if 'relations_and_types_merged' in analyzer.merged_data:
                    st.write("**📊 Relations + Types (İlişkiler + Tipler):**")
                    rel_types_df = pd.DataFrame(analyzer.merged_data['relations_and_types_merged'])
                    st.dataframe(rel_types_df, use_container_width=True, height=300)

                # Baş-Uç İlişki Görselleştirmesi - Streamlit-Agraph
                if 'relations_merged' in analyzer.merged_data and 'entity_types_merged' in analyzer.merged_data:
                    st.subheader("🎯 İnteraktif Cytoscape Graf Ağı")
                    st.info("""
                    **� İnteraktif Graf Özellikleri:**
                    - 🔵 **Mavi Düğümler**: Kaynak varlıklar (Baş) + Entity tipleri
                    - 🔴 **Kırmızı Düğümler**: Hedef varlıklar (Uç) + Entity tipleri  
                    - 🟢 **Yeşil Kenarlar**: Semantik ilişkiler (hover ile detay)
                    - �️ **İnteraktif**: Düğümleri sürükle, zoom yap, hover ile bilgi gör
                    - ⚡ **Fizik Simulasyonu**: Otomatik düğüm yerleşimi ve animasyon
                    """)
                    
                    # Entity types mapping oluştur
                    entity_types_map = {}
                    for entity_record in analyzer.merged_data['entity_types_merged']:
                        entity_name = entity_record.get('entity', '')
                        entity_type = entity_record.get('entity_type', '')
                        entity_types_map[entity_name] = entity_type
                    
                    # Relations verisini al
                    relations_data = analyzer.merged_data['relations_merged']
                    total_relations = len(relations_data)
                    
                    # Sayfalama kontrolü ve ayarlar
                    # Sayfalama kaldırıldı - tüm ilişkileri göster
                    page_relations = relations_data
                    
                    st.write(f"**İlişki Ağı** - Toplam: {len(page_relations)} ilişki çifti")
                    
                    # Graf görselleştirme kodu kaldırıldı - sadece tablo görünümü kullanılıyor
                    # Stylesheet kodu kaldırıldı
                    
                    # Sadece tablo görünümü - Graf görselleştirmeleri kaldırıldı
                    st.write("📊 **Tablo Görünümü**")
                    for idx, row in enumerate(page_relations):
                        head = row.get('baş', '')
                        tail = row.get('uç', '')
                        relations = row.get('ilişki', '')
                        head_types = entity_types_map.get(head, '')
                        tail_types = entity_types_map.get(tail, '')
                        
                        col1, col2, col3 = st.columns([3, 2, 3])
                        with col1:
                            st.write(f"🔵 **{head}**")
                            st.caption(f"_{head_types}_")
                        with col2:
                            st.write(f"➡️ _{relations}_")
                        with col3:
                            st.write(f"🔴 **{tail}**")
                            st.caption(f"_{tail_types}_")
                        
                        if idx < len(page_relations) - 1:
                            st.divider()
                    
                    # İstatistikler
                    col1, col2 = st.columns(2)
                    with col1:
                        # Benzersiz entity sayısını hesapla
                        unique_entities = set([r.get('baş','') for r in page_relations] + [r.get('uç','') for r in page_relations])
                        st.metric("📊 Düğüm Sayısı", len(unique_entities))
                    with col2:
                        # İlişki sayısını hesapla
                        st.metric("🔗 İlişki Sayısı", len(page_relations))
        
        # 7. Orijinal Veri İstatistikleri
        st.markdown("---")
        st.header("📊 Orijinal Veri İstatistikleri")
        
        # İlişki türü analizi
        relation_stats = defaultdict(int)
        entity_type_stats = defaultdict(int)
        
        for file_name, triples in analyzer.data.items():
            for triple in triples:
                relation_stats[triple.get('ilişki', 'Bilinmiyor')] += 1
                entity_type_stats[triple.get('baş_tipi', 'Bilinmiyor')] += 1
                entity_type_stats[triple.get('uç_tipi', 'Bilinmiyor')] += 1
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**En Sık Kullanılan İlişkiler:**")
            top_relations = sorted(relation_stats.items(), key=lambda x: x[1], reverse=True)[:10]
            for relation, count in top_relations:
                st.write(f"• {relation}: {count} kez")
        
        with col2:
            st.write("**En Sık Kullanılan Varlık Türleri:**")
            top_entity_types = sorted(entity_type_stats.items(), key=lambda x: x[1], reverse=True)[:10]
            for entity_type, count in top_entity_types:
                st.write(f"• {entity_type}: {count} kez")
    
    else:
        st.info("👆 Lütfen önce JSON dosyalarını yükleyin.")
        st.markdown("""
        ### 📋 Kullanım Talimatları:
        1. **Klasör Yolu**: JSON dosyalarınızın bulunduğu klasör yolunu girin
        2. **Dosyaları Yükle**: Butona tıklayarak dosyaları yükleyin
        3. **Analiz**: Yükleme sonrası otomatik olarak analizler görüntülenir
        
        ### 📄 Desteklenen Dosya Formatı:
        ```json
        [
            {
                "metin": "Açıklama metni",
                "baş": "Varlık adı",
                "baş_tipi": "Varlık tipi",
                "ilişki": "İlişki türü",
                "uç": "Hedef varlık",
                "uç_tipi": "Hedef varlık tipi"
            }
        ]
        ```
        """)

if __name__ == "__main__":
    main()