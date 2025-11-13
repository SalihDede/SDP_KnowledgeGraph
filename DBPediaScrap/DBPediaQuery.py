import json
import os
import sys
from SPARQLWrapper import SPARQLWrapper, JSON
from urllib.parse import urlparse

def get_dbpedia_triples(endpoint_url, query):
    """
    SPARQL sorgusunu çalıştırır ve sonuçları işler.
    """
    sparql = SPARQLWrapper(endpoint_url)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    
    try:
        results = sparql.query().convert()
        formatted_triples = []
        bindings = results["results"]["bindings"]
        
        seen_triples = set()

        for item in bindings:
            # Güvenli veri çekme
            bas = item.get('bas_label', {}).get('value', 'Bilinmiyor')
            iliski = item.get('iliski_label', {}).get('value', 'Bilinmiyor')
            
            # Değer Garantisi: Final varsa al, yoksa Raw, o da yoksa 'Belirsiz'
            final_val = item.get('final_uc_value', {}).get('value')
            raw_val = item.get('raw_value', {}).get('value')
            
            uc = final_val if final_val else raw_val
            if not uc:
                uc = "Belirsiz Değer"

            # Tip bilgisini al
            uc_tip = item.get('final_uc_type', {}).get('value', 'Veri/Literal')
            
            # Baş tipleri
            bas_tip = item.get('bas_tipleri', {}).get('value', 'Varlık')

            triple_key = (bas, iliski, uc)
            
            if triple_key not in seen_triples:
                seen_triples.add(triple_key)
                
                formatted_item = {
                    "baş": bas,
                    "baş_tipi": bas_tip,
                    "ilişki": iliski,
                    "uç": uc,
                    "uç_tipi": uc_tip
                }
                formatted_triples.append(formatted_item)
                
        return formatted_triples

    except Exception as e:
        print(f"SPARQL sorgusu çalıştırılırken bir hata oluştu: {e}")
        return None

def create_sparql_query(entity_uri):
    """
    Düzeltilmiş Sorgu: Parantez hataları giderildi.
    """
    sparql_query = f"""
    PREFIX dbr: <http://dbpedia.org/resource/>
    PREFIX dbo: <http://dbpedia.org/ontology/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT DISTINCT 
        ?bas_label 
        ?iliski_label 
        ?final_uc_value 
        ?raw_value 
        ?final_uc_type 
        (GROUP_CONCAT(DISTINCT ?bas_tip_simple; separator=", ") AS ?bas_tipleri)
    WHERE {{
        VALUES ?bas {{ {entity_uri} }}
        
        {{
            # --- 1. BOLUM: STANDART ILISKILER ---
            ?bas ?iliski ?uc .
            
            FILTER(STRSTARTS(STR(?iliski), "http://dbpedia.org/ontology/"))
            FILTER(?iliski NOT IN (
                dbo:wikiPageWikiLink, dbo:wikiPageRedirects, dbo:wikiPageExternalLink, 
                dbo:thumbnail, dbo:abstract, dbo:wikiPageID, dbo:wikiPageRevisionID,
                dbo:careerStation, dbo:wikiPageDisambiguates
            ))
            FILTER(!isLiteral(?uc) || (LANG(?uc) = "" || LANG(?uc) = "tr" || LANG(?uc) = "en"))

            BIND(?iliski AS ?real_relation)
            BIND(?uc AS ?real_target)
        }}
        UNION
        {{
            # --- 2. BOLUM: DERIN KARIYER DETAYLARI ---
            ?bas dbo:careerStation ?station .
            ?station ?stat_rel ?stat_val .
            FILTER(?stat_rel IN (dbo:team, dbo:years, dbo:numberOfGoals, dbo:numberOfMatches))
            BIND(IRI(CONCAT("http://dbpedia.org/ontology/career_", LCASE(REPLACE(STR(?stat_rel), "http://dbpedia.org/ontology/", "")))) AS ?real_relation)
            BIND(?stat_val AS ?real_target)
        }}

        # --- ETİKETLER ---
        OPTIONAL {{ ?bas rdfs:label ?bl_tr . FILTER(LANG(?bl_tr) = "tr") }}
        BIND(COALESCE(?bl_tr, STRAFTER(STR(?bas), "/resource/")) AS ?bas_label)

        OPTIONAL {{ ?real_relation rdfs:label ?rl_tr . FILTER(LANG(?rl_tr) = "tr") }}
        BIND(REPLACE(STR(?real_relation), "http://dbpedia.org/ontology/", "") AS ?rel_raw)
        BIND(COALESCE(?rl_tr, ?rel_raw) AS ?iliski_label)

        # --- UC DEGERI COZUMLEME ---
        BIND(STR(?real_target) AS ?raw_value)

        OPTIONAL {{ FILTER(ISIRI(?real_target)) ?real_target rdfs:label ?ul_tr . FILTER(LANG(?ul_tr) = "tr") }}
        OPTIONAL {{ FILTER(ISIRI(?real_target)) ?real_target rdfs:label ?ul_en . FILTER(LANG(?ul_en) = "en") }}
        
        BIND(IF(ISIRI(?real_target), STRAFTER(STR(?real_target), "/resource/"), ?raw_value) AS ?uri_clean)
        BIND(COALESCE(?ul_tr, ?ul_en, ?uri_clean) AS ?final_uc_value)

        # --- TIP COZUMLEME (Parantez Hatasi Duzeltildi) ---
        
        OPTIONAL {{
            FILTER(ISIRI(?real_target))
            ?real_target rdf:type ?uc_class .
            FILTER(STRSTARTS(STR(?uc_class), "http://dbpedia.org/ontology/"))
            FILTER(?uc_class NOT IN (dbo:Agent, dbo:Thing))
        }}
        
        BIND(DATATYPE(?real_target) AS ?uc_datatype)

        # Zincirleme REPLACE yerine daha temiz yapi
        BIND(
            IF(BOUND(?uc_class), 
               REPLACE(STR(?uc_class), "http://dbpedia.org/ontology/", ""), 
               IF(BOUND(?uc_datatype), 
                  REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(STR(?uc_datatype), 
                  "http://www.w3.org/2001/XMLSchema#", ""), 
                  "integer", "Tam Sayi"), 
                  "date", "Tarih"), 
                  "string", "Metin"),
                  "anyURI", "Metin"), 
                  "gYear", "Yil"),
                  "Veri/Literal"
               )
            ) 
        AS ?final_uc_type)
        
        # Bas Tipleri
        OPTIONAL {{
            ?bas rdf:type ?bas_tip .
            FILTER(STRSTARTS(STR(?bas_tip), "http://dbpedia.org/ontology/"))
            FILTER(?bas_tip NOT IN (dbo:Agent, dbo:Thing))
        }}
        BIND(REPLACE(STR(?bas_tip), "http://dbpedia.org/ontology/", "") AS ?bas_tip_simple)

    }}
    GROUP BY ?bas_label ?iliski_label ?final_uc_value ?raw_value ?final_uc_type
    LIMIT 1000
    """
    return sparql_query

# --- Ana Program ---
endpoint_url = "https://dbpedia.org/sparql"

try:
    script_directory = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_directory = os.path.abspath(os.getcwd())

output_directory = os.path.join(script_directory, "DBpediaOutputs")

input_url = input("Lutfen bir DBpedia resource URL'si girin (orn: http://dbpedia.org/resource/Lamine_Yamal):\\n> ")

try:
    parsed_url = urlparse(input_url)
    entity_name = parsed_url.path.split('/')[-1]
    
    if not entity_name:
        print("Hata: Gecerli bir varlik adi URL'den alinamadi.")
        sys.exit()
        
    # URL 'page' olsa bile 'resource' (dbr:) prefixi ile calisir
    target_entity_uri = f"dbr:{entity_name}"
    print(f"'{entity_name}' varligi icin veriler cekiliyor...")

    query = create_sparql_query(target_entity_uri)
    triples_data = get_dbpedia_triples(endpoint_url, query)

    if triples_data:
        os.makedirs(output_directory, exist_ok=True)
        output_filename = f"{entity_name}_triples.json"
        output_filepath = os.path.join(output_directory, output_filename)
        
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(triples_data, f, ensure_ascii=False, indent=4)
            
        print(f"\\nBasarili! Toplam {len(triples_data)} adet veri bulundu.")
        print(f"Dosya: {output_filepath}")
        
    else:
        print(f"Veri bulunamadi.")

except Exception as e:
    print(f"Hata: {e}")