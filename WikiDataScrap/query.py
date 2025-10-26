#!/usr/bin/env python3

"""
Wikidata Entity Explorer & Extractor (Automated File Output)

This script takes a single Wikidata Q-number, retrieves all of its
direct properties and values, and then performs two actions:
1. Displays all relations in a human-readable format on the screen.
2. Extracts all discovered Q-numbers AND the original Q-number,
   and saves them to a file named after the Q-ID inside a 'related_entities' folder.
"""

import requests
import sys
import os

# The public SPARQL endpoint for Wikidata
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# A descriptive User-Agent is required by the Wikidata API policy.
HEADERS = {
    'User-Agent': 'MyKnowledgeGraphProject/1.0 (contact@example.com)'
}

def get_user_input():
    """Prompts the user for just the Q-number."""
    print("--- Wikidata Entity Explorer & Extractor ---")
    print("This will find all relations for an entity and save related Q-numbers to a file.\n")
    
    q_number = ""
    while not (q_number.startswith('Q') and q_number[1:].isdigit()):
        q_number = input("Enter the entity's Q-number to explore (e.g., Q615): ").strip().upper()
        
    return q_number

def build_sparql_query(q_number):
    """Constructs a SPARQL query to find all properties and values for a given Q-number."""
    query = f"""
    SELECT ?propLabel ?value ?valueLabel WHERE {{
      wd:{q_number} ?p ?value.
      ?prop wikibase:directClaim ?p.
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "tr". }}
    }}
    ORDER BY ?propLabel
    """
    return query

def process_and_save_results(data, q_number, filename):
    """
    Parses data, displays all relations, and saves the original and related
    entity Q-numbers to the specified file path.
    """
    if not data:
        print("No data to parse.")
        return

    try:
        results = data['results']['bindings']
        if not results:
            print(f"No relations found for {q_number}.")
        
        print("\n" + "="*50)
        print(f"Displaying {len(results)} relations for {q_number}:")
        print("="*50)
        
        related_q_numbers = set()

        for item in results:
            prop_label = item.get('propLabel', {}).get('value', 'N/A')
            value_uri = item.get('value', {}).get('value', '')
            value_label = item.get('valueLabel', {}).get('value', value_uri)

            if 'http://www.wikidata.org/entity/Q' in value_uri:
                q_id = value_uri.split('/')[-1]
                related_q_numbers.add(q_id)
                print(f"- {q_number} --- ({prop_label}) ---> {value_label} ({q_id})")
            else:
                print(f"- {q_number} --- ({prop_label}) ---> {value_label}")

        print("\n" + "="*50)

        # --- KEY CHANGE IS HERE ---
        # Combine the discovered Q-IDs with the original input Q-ID.
        all_q_ids_to_save = related_q_numbers | {q_number}

        print(f"\nFound {len(related_q_numbers)} related entities.")
        print(f"Saving a total of {len(all_q_ids_to_save)} Q-IDs to '{filename}'...")

        with open(filename, 'w', encoding='utf-8') as f:
            # Sort the combined list for consistent output
            for q_id in sorted(list(all_q_ids_to_save)):
                f.write(q_id + '\n')
        
        print(f"✅ Successfully saved file. '{filename}' is now ready for Phase 2.")

    except KeyError:
        print("❌ Error: Could not parse the JSON response.")
    except IOError as e:
        print(f"❌ Error writing to file '{filename}': {e}")


def main():
    """Main function to run the script."""
    try:
        # Step 1: Get the Q-number from the user
        q_number = get_user_input()
        
        # Step 2: Define the output directory and create it if it doesn't exist
        output_dir = "WikiDataScrap/related_entities"
        if not os.path.exists(output_dir):
            print(f"Directory '{output_dir}' not found. Creating it...")
            os.makedirs(output_dir)
        
        # Step 3: Automatically generate the full file path
        filename = os.path.join(output_dir, f"{q_number}.txt")
        
        # Step 4: Fetch data from Wikidata
        print(f"\n🚀 Fetching relations for {q_number}...")
        query = build_sparql_query(q_number)
        response = requests.get(SPARQL_ENDPOINT, params={'query': query, 'format': 'json'}, headers=HEADERS)
        response.raise_for_status()
        print("✅ Query successful!")
        json_data = response.json()
        
        # Step 5: Process the results and save to the generated file path
        process_and_save_results(json_data, q_number, filename)
        
    except requests.exceptions.RequestException as e:
        print(f"❌ An error occurred: {e}")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting.")
        sys.exit(0)

if __name__ == "__main__":
    main()