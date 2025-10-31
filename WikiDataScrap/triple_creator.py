#!/usr/bin/env python3

"""
Wikidata Relationship Triple Extractor

This script takes a single Wikidata Q-number and generates a JSON file
containing all its direct relationships in the format:
{
  "baş": "Source Label", "baş_tipi": "Source Type",
  "ilişki": "Relation Label",
  "uç": "Target Label", "uç_tipi": "Target Type"
}
"""

import requests
import sys
import os
import json

# The public SPARQL endpoint for Wikidata
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# A descriptive User-Agent is required by the Wikidata API policy.
HEADERS = {
    'User-Agent': 'MyKnowledgeGraphProject/1.0 (contact@example.com)'
}

def get_user_input():
    """Prompts the user for the Q-number."""
    print("--- Wikidata Relationship Triple Extractor ---")
    q_number = ""
    while not (q_number.startswith('Q') and q_number[1:].isdigit()):
        q_number = input("Enter the entity's Q-number (e.g., Q615 for Lionel Messi): ").strip().upper()
    return q_number

def build_sparql_query(q_number):
    """
    Constructs a SPARQL query to find all necessary components for the triple.
    - Source Label (?sourceLabel)
    - Source Type (?sourceTypeLabel)
    - Property Label (?propLabel)
    - Target Label (?targetLabel)
    - Target Type (?targetTypeLabel)
    """
    query = f"""
    SELECT
      ?sourceLabel
      ?sourceTypeLabel
      ?propLabel
      ?targetLabel
      ?targetTypeLabel
    WHERE {{
      BIND(wd:{q_number} AS ?source)

      # Get direct relationships where the target is also a Wikidata entity
      ?source ?p ?target.
      ?prop wikibase:directClaim ?p.
      FILTER(isIRI(?target) && CONTAINS(STR(?target), "http://www.wikidata.org/entity/Q"))

      # Get the type (P31) for the source and target entities (optional)
      OPTIONAL {{ ?source wdt:P31 ?sourceType. }}
      OPTIONAL {{ ?target wdt:P31 ?targetType. }}

      # Get all labels in Turkish (with English fallback handled in Python)
      SERVICE wikibase:label {{
        bd:serviceParam wikibase:language "tr,en".
        ?source rdfs:label ?sourceLabel.
        ?sourceType rdfs:label ?sourceTypeLabel.
        ?prop rdfs:label ?propLabel.
        ?target rdfs:label ?targetLabel.
        ?targetType rdfs:label ?targetTypeLabel.
      }}
    }}
    ORDER BY ?propLabel ?targetLabel
    """
    return query

def process_and_save_results(data, q_number, filename):
    """Parses SPARQL results and saves them into the desired JSON format."""
    if not data or not data['results']['bindings']:
        print(f"❌ No relationships found for {q_number}.")
        return

    results = data['results']['bindings']
    triples_list = []

    print(f"\nProcessing {len(results)} relationships found for {q_number}...")

    for item in results:
        # Create a dictionary for the current triple
        triple = {
            "baş": item.get('sourceLabel', {}).get('value', q_number),
            "baş_tipi": item.get('sourceTypeLabel', {}).get('value', 'Belirtilmemiş'), # "Not specified"
            "ilişki": item.get('propLabel', {}).get('value', 'Bilinmeyen İlişki'), # "Unknown Relation"
            "uç": item.get('targetLabel', {}).get('value', 'Bilinmeyen Varlık'), # "Unknown Entity"
            "uç_tipi": item.get('targetTypeLabel', {}).get('value', 'Belirtilmemiş') # "Not specified"
        }
        triples_list.append(triple)
        
    # Save the list of triples to a JSON file
    try:
        output_dir = "WikiDataScrap/json_outputs"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(triples_list, f, indent=4, ensure_ascii=False)
            
        print(f"\n✅ Successfully saved {len(triples_list)} triples to '{filepath}'.")
    except IOError as e:
        print(f"❌ Error writing to file '{filepath}': {e}")


def main():
    """Main function to run the script."""
    try:
        q_number = get_user_input()
        
        # Automatically generate the JSON filename
        filename = f"{q_number}_triples.json"
        
        print(f"\n🚀 Fetching relationships for {q_number}...")
        query = build_sparql_query(q_number)
        response = requests.get(SPARQL_ENDPOINT, params={'query': query, 'format': 'json'}, headers=HEADERS)
        response.raise_for_status()
        print("✅ Query successful!")
        
        json_data = response.json()
        process_and_save_results(json_data, q_number, filename)

    except requests.exceptions.RequestException as e:
        print(f"❌ An error occurred during the request: {e}")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting.")
        sys.exit(0)

if __name__ == "__main__":
    main()