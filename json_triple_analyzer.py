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
    
    if st.sidebar.button("📂 Dosyaları Yükle", type="primary"):
        if os.path.exists(folder_path):
            if analyzer.load_json_files(folder_path):
                st.session_state.analyzer = analyzer
                st.session_state.data_loaded = True
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
        st.info("ℹ️ Bu analizde sadece 'baş', 'ilişki' ve 'uç' değerlerinin tamamen aynı olduğu triple'lar kesişim olarak kabul edilir.")
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
            
            # Detaylı entity cluster analizi
            st.subheader("🔍 Varlık Kümeleri (Entity Clusters)")
            
            # Similarity threshold ayarı
            similarity_threshold = st.slider(
                "Benzerlik Eşiği (%)", 
                min_value=70, 
                max_value=100, 
                value=85, 
                step=5,
                help="Daha düşük değerler daha fazla benzer varlık bulur"
            )
            
            if st.button("🔄 Benzerlik Eşiğini Yeniden Hesapla"):
                with st.spinner("Yeniden hesaplanıyor..."):
                    # Tüm varlıkları topla
                    all_entities = set()
                    for triples in analyzer.data.values():
                        for triple in triples:
                            all_entities.add(triple.get('baş', ''))
                            all_entities.add(triple.get('uç', ''))
                    
                    # Yeni threshold ile clusters'ları hesapla
                    new_clusters = analyzer.find_similar_entities(all_entities, similarity_threshold)
                    
                    # Sadece 1'den fazla varlık içeren cluster'ları göster
                    multi_entity_clusters = {k: v for k, v in new_clusters.items() if len(v) > 1}
                    
                    if multi_entity_clusters:
                        st.success(f"✅ {len(multi_entity_clusters)} varlık kümesi bulundu!")
                        
                        for cluster_head, entities in list(multi_entity_clusters.items())[:15]:  # İlk 15 küme
                            with st.expander(f"📊 {cluster_head} ({len(entities)} varlık)"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write("**Kümedeki Varlıklar:**")
                                    for entity in entities:
                                        st.write(f"• {entity}")
                                with col2:
                                    # Bu varlıkların hangi dosyalarda geçtiğini göster
                                    file_occurrence = {}
                                    for file_name, triples in analyzer.data.items():
                                        count = 0
                                        for triple in triples:
                                            if triple.get('baş', '') in entities or triple.get('uç', '') in entities:
                                                count += 1
                                        if count > 0:
                                            file_occurrence[file_name] = count
                                    
                                    if file_occurrence:
                                        st.write("**Dosyalardaki Geçiş Sayıları:**")
                                        for file_name, count in file_occurrence.items():
                                            st.write(f"• {file_name}: {count} kez")
                        
                        if len(multi_entity_clusters) > 15:
                            st.info(f"... ve {len(multi_entity_clusters) - 15} küme daha.")
                    else:
                        st.warning("Bu benzerlik eşiği ile benzer varlık kümesi bulunamadı.")
        else:
            st.info("Farklı ilişkilere sahip benzer varlık bulunamadı.")
        
        # 6. İstatistikler
        st.markdown("---")
        st.header("📊 Genel İstatistikler")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Dosya Karşılaştırması")
            comparison_data = {
                'Dosya': file_names,
                'Triple Sayısı': [len(analyzer.triple_sets[name]) for name in file_names]
            }
            df_comparison = pd.DataFrame(comparison_data)
            
            fig_bar = px.bar(
                df_comparison, 
                x='Dosya', 
                y='Triple Sayısı',
                title="Dosyalardaki Triple Sayıları",
                color='Triple Sayısı',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with col2:
            st.subheader("🥧 Kesişim Dağılımı")
            intersection_data = {
                'Kesişim': list(intersections.keys()),
                'Sayı': [len(intersection_set) for intersection_set in intersections.values()]
            }
            df_intersections = pd.DataFrame(intersection_data)
            
            if not df_intersections.empty:
                fig_pie = px.pie(
                    df_intersections, 
                    values='Sayı', 
                    names='Kesişim',
                    title="Kesişim Türlerinin Dağılımı"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
        
        # Ek istatistikler
        st.subheader("📈 Detaylı İstatistikler")
        
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