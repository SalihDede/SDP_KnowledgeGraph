from typing import List
from scipy.spatial.distance import cdist
from concurrent.futures import ThreadPoolExecutor
import dspy
from kg_gen.models import Graph
import logging
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.cluster import KMeans


class LLMDeduplicate:
    graph: Graph
    nodes: list[str]
    edges: list[str]
    node_clusters: list[list[str]]
    edge_clusters: list[list[str]]
    retrieval_model: SentenceTransformer
    lm: dspy.LM

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, retrieval_model: SentenceTransformer, lm: dspy.LM, graph: Graph):
        """
        Önbelleğe alınmış gömülemeler, BM25 belirteçleri ve metin parçası deposu ile BG destekli RAG'ı başlat.
        """
        self.graph = graph
        self.nodes = list(graph.entities)
        self.edges = list(graph.edges)
        self.node_clusters = graph.entity_clusters or []
        self.edge_clusters = graph.edge_clusters or []
        self.retrieval_model = retrieval_model
        self.lm = lm

        # Düğümler için gömülemeler ve BM25 belirteçleri
        self.node_embeddings = retrieval_model.encode(
            self.nodes, show_progress_bar=True
        )
        self.node_bm25_tokenized = [text.lower().split() for text in self.nodes]

        # BM25'i belirteçlerden her zaman yeniden oluştur (hızlıdır ve nesneyi serileştirmekten daha basittir)
        self.node_bm25 = BM25Okapi(self.node_bm25_tokenized)

        # Kenarlar için gömülemeler ve BM25 belirteçleri
        self.edge_embeddings = retrieval_model.encode(
            self.edges, show_progress_bar=True
        )
        self.edge_bm25_tokenized = [text.lower().split() for text in self.edges]

        # BM25'i belirteçlerden her zaman yeniden oluştur
        self.edge_bm25 = BM25Okapi(self.edge_bm25_tokenized)

        dspy.configure(lm=lm)

    def get_relevant_items(
        self, query: str, top_k: int = 50, type: str = "node"
    ) -> list[str]:
        """
        En iyi k düğümü almak için BM25 + gömüleme sıralama birleşimini kullan.
        """
        query_tokens = query.lower().split()

        # BM25
        bm25_scores = (
            self.node_bm25.get_scores(query_tokens)
            if type == "node"
            else self.edge_bm25.get_scores(query_tokens)
        )

        # Gömüleme
        query_embedding = self.retrieval_model.encode([query], show_progress_bar=False)
        embeddings = self.node_embeddings if type == "node" else self.edge_embeddings
        embedding_scores = cosine_similarity(query_embedding, embeddings).flatten()

        # Sıralama birleşimi (eşit ağırlıklandırma)
        combined_scores = 0.5 * bm25_scores + 0.5 * embedding_scores
        top_indices = np.argsort(combined_scores)[::-1][:top_k]
        items = self.nodes if type == "node" else self.edges
        top_items = [items[i] for i in top_indices]

        return top_items

    def cluster(self):
        cluster_size = 128

        embedding_sets = {"node": self.node_embeddings, "edge": self.edge_embeddings}

        for embedding_type, embeddings in embedding_sets.items():
            n_samples = len(embeddings)
            num_clusters = max(1, n_samples // cluster_size)

            # Adım 1: Küme merkezleri
            kmeans = KMeans(
                n_clusters=num_clusters,
                init="random",
                n_init=1,
                max_iter=20,
                tol=0.0,
                algorithm="lloyd",
                verbose=True,
            )
            kmeans.fit(embeddings.astype(np.float32))
            centroids = kmeans.cluster_centers_

            # Adım 2: Her noktayı en yakın merkeze ata (küme başına maksimum 25)
            distances = cdist(embeddings, centroids)
            assignments = np.argsort(distances, axis=1)

            # Küme takibini başlat
            clusters: List[List[int]] = [[] for _ in range(num_clusters)]
            assigned = np.zeros(n_samples, dtype=bool)

            for rank in range(num_clusters):
                for i in range(n_samples):
                    if assigned[i]:
                        continue
                    cluster_id = assignments[i, rank]
                    if len(clusters[cluster_id]) < cluster_size:
                        clusters[cluster_id].append(i)
                        assigned[i] = True

            unassigned = np.where(~assigned)[0]

            # Varsa atanmamış öğeleri kendi kümeleri olarak ekle
            if len(unassigned) > 0:
                self.logger.debug(
                    "%s atanmamış öğe ayrı bir küme olarak ekleniyor", len(unassigned)
                )
                clusters.append(unassigned.tolist())
            else:
                self.logger.debug("Küme olarak eklenecek atanmamış öğe yok")

            # Kümeleri JSON dosyalarına kaydet
            cluster_type = embedding_type  # 'node' veya 'edge'

            # Kümeler hakkında hata ayıklama bilgilerini yazdır
            self.logger.debug("%s küme sayısı: %s", cluster_type, len(clusters))
            self.logger.debug("İlk küme boyutu: %s", len(clusters[0]))
            self.logger.debug("İlk kümedeki ilk birkaç öğe: %s", clusters[0][:5])
            self.logger.debug("Son küme boyutu: %s", len(clusters[-1]))
            self.logger.debug(
                "Küme boyutlarının dağılımı: %s...",
                [len(clust) for clust in clusters[:5]],
            )

            # Kümeleri JSON serileştirilebilir formata dönüştür - indeksler yerine adları kaydet
            if cluster_type == "node":
                self.logger.debug("Düğüm indeksleri düğüm adlarına dönüştürülüyor...")
                clusters_data = [
                    [self.nodes[idx] for idx in cluster] for cluster in clusters
                ]
                self.logger.debug(
                    "Dönüştürme sonrası ilk küme örneği: %s", clusters_data[0][:3]
                )
                # Düğüm kümelerini self'e ekle
                self.node_clusters = clusters_data
            else:  # edge
                self.logger.debug("Kenar kümeleri işleniyor...")
                clusters_data = [
                    [self.edges[idx] for idx in cluster] for cluster in clusters
                ]
                self.logger.debug(
                    "Kenar kümeleri verisi boş: %s", len(clusters_data) == 0
                )
                # Kenar kümelerini self'e ekle
                self.edge_clusters = clusters_data

    def deduplicate_cluster(
        self, cluster: list[str], type: str = "node"
    ) -> tuple[set, dict[str, list[str]]]:
        cluster = cluster.copy()

        items = set()
        item_clusters = {}
        plural_type = "varlıklar" if type == "node" else "kenarlar"
        singular_type = "varlık" if type == "node" else "kenar"

        self.logger.info(
            "Kümedeki %s %s için tekilleştirme başlatılıyor", len(cluster), plural_type
        )

        processed_count = 0
        while len(cluster) > 0:
            processed_count += 1
            item = cluster.pop()

            self.logger.debug(
                "[%s/%s] İşleniyor %s: '%s'",
                processed_count,
                len(cluster),
                singular_type,
                item,
            )

            relevant_items = self.get_relevant_items(item, 16, type)

            self.logger.debug(
                "  '%s' için %s ilgili %s bulundu",
                item,
                len(relevant_items),
                plural_type,
            )
            if len(relevant_items) > 0:
                self.logger.debug(
                    "  Örnek ilgili öğeler: %s%s",
                    relevant_items[:3],
                    ("..." if len(relevant_items) > 3 else ""),
                )

            class Deduplicate(dspy.Signature):
                __doc__ = f"""Öğe için yinelenen {plural_type} ve yinelenenleri en iyi temsil eden bir takma ad bul. Yinelenenler, zaman kipi, çoğul form, kök form, büyük/küçük harf, kısaltma, stenografi gibi varyasyonlarla anlam olarak aynı olanlardır. Hiç yoksa boş liste döndür.
                """
                item: str = dspy.InputField()
                set: list[str] = dspy.InputField()
                duplicates: list[str] = dspy.OutputField(
                    description="{plural_type} kümesindeki öğelerle tam eşleşmeler"
                )
                alias: str = dspy.OutputField(
                    description=f"Yinelenenleri temsil edecek en iyi {singular_type} adı, tercihen {plural_type} kümesinden"
                )

            # with dspy.context(lm=self.lm):
            deduplicate = dspy.Predict(Deduplicate)
            result = deduplicate(item=item, set=relevant_items)
            items.add(result.alias)

            # Yinelenenleri yalnızca kümede bulunanları içerecek şekilde filtrele
            duplicates = [dup for dup in result.duplicates if dup in cluster]

            if len(duplicates) > 0:
                self.logger.debug(
                    "  ✓ '%s' için %s yinelenen bulundu", item, len(duplicates)
                )
                self.logger.info(
                    "  → '%s' ve %s'i temsil etmek için '%s' takma adı kullanılıyor",
                    item,
                    duplicates,
                    result.alias,
                )
                item_clusters[result.alias] = {item}
                for duplicate in duplicates:
                    cluster.remove(duplicate)
                    item_clusters[result.alias].add(duplicate)
            else:
                self.logger.debug(
                    "  ✗ '%s' için yinelenen bulunamadı, olduğu gibi tutuluyor", item
                )
                item_clusters[item] = {item}

        self.logger.debug(
            "Tekilleştirme tamamlandı: orijinal %s'den %s benzersiz %s",
            processed_count,
            len(items),
            plural_type,
        )

        return items, item_clusters

    def deduplicate(self) -> Graph:
        # Ara ilerleme varsa kontrol et ve yükle
        entities = set()
        edges = set()
        entity_clusters = {}
        edge_clusters = {}

        pool = ThreadPoolExecutor(max_workers=64)

        # Düğüm kümelerini paralel olarak işle
        node_futures = []
        cnt_nodes = 0
        for i, cluster in enumerate(self.node_clusters):
            cnt_nodes += len(cluster)
            node_futures.append(pool.submit(self.deduplicate_cluster, cluster, "node"))

        # Kenar kümelerini paralel olarak işle
        edge_futures = []
        cnt_edges = 0
        for i, cluster in enumerate(self.edge_clusters):
            cnt_edges += len(cluster)
            edge_futures.append(pool.submit(self.deduplicate_cluster, cluster, "edge"))

        # Düğüm future'larından sonuçları topla
        for i, future in enumerate(node_futures):
            try:
                cluster_entities, cluster_entity_map = future.result()
                entities.update(cluster_entities)
                entity_clusters.update(cluster_entity_map)
            except Exception as e:
                self.logger.error("Düğüm kümesi %s işlenirken hata: %s", i, e)

        # Kenar future'larından sonuçları topla
        for i, future in enumerate(edge_futures):
            try:
                cluster_edges, cluster_edge_map = future.result()
                edges.update(cluster_edges)
                edge_clusters.update(cluster_edge_map)
            except Exception as e:
                self.logger.error("Kenar kümesi %s işlenirken hata: %s", i, e)

        self.logger.info(
            "Tüm kümeler %s düğüm ve %s kenar LLM çağrısıyla işlendi",
            cnt_nodes,
            cnt_edges,
        )

        # Kümelere göre ilişkileri güncelle
        relations: set[tuple[str, str, str]] = set()

        for s, p, o in self.graph.relations:
            # Özneyi varlık kümelerinde ara
            if s not in entities:
                for rep, cluster in entity_clusters.items():
                    if s in cluster:
                        s = rep
                        break

            # Yüklemi kenar kümelerinde ara
            if p not in edges:
                for rep, cluster in edge_clusters.items():
                    if p in cluster:
                        p = rep
                        break

            # Nesneyi varlık kümelerinde ara
            if o not in entities:
                for rep, cluster in entity_clusters.items():
                    if o in cluster:
                        o = rep
                        break

            relations.add((s, p, o))

        # Tekilleştirilmiş varlık adlarıyla eşleşecek şekilde entity_metadata anahtarlarını güncelle
        new_entity_metadata: dict[str, set[str]] | None = None
        if self.graph.entity_metadata:
            new_entity_metadata = {}
            for original_entity, metadata_set in self.graph.entity_metadata.items():
                # Bu varlık için tekilleştirilmiş temsilciyi bul
                deduped_entity = original_entity
                for rep, cluster in entity_clusters.items():
                    if original_entity in cluster:
                        deduped_entity = rep
                        break
                # Varlıklar birlikte tekilleştirildiğinde metadata kümelerini birleştir
                if deduped_entity in new_entity_metadata:
                    new_entity_metadata[deduped_entity].update(metadata_set)
                else:
                    new_entity_metadata[deduped_entity] = metadata_set.copy()

        # Tekilleştirilmiş verilerle yeni Graph örneği oluştur
        deduped_graph = Graph(
            entities=entities,
            edges=edges,
            relations=relations,
            entity_clusters=entity_clusters,
            edge_clusters=edge_clusters,
            entity_metadata=new_entity_metadata,
        )

        return deduped_graph