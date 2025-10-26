#!/usr/bin/env python3

"""
Phase 2: Detailed Data Scraping with the API (Automated File Output)

This script takes a file containing a list of Wikidata Q-numbers (one per line),
fetches the detailed data for each entity using the Wikidata API, and saves
the enriched data to a new JSON file named after the input Q-ID inside a
'detailed_info' folder.

It uses batching to efficiently query the API for up to 50 entities at a time.
"""

import requests
import sys
import json
import time
import os # <-- Added for file/directory operations

# The API endpoint for Wikidata
API_ENDPOINT = "https://www.wikidata.org/w/api.php"

# A descriptive User-Agent is required by the API policy.
HEADERS = {
    'User-Agent': 'MyKnowledgeGraphProject/1.0 (contact@example.com)'
}

def get_user_input():
    """Prompts the user for only the input filename."""
    print("--- Wikidata Detailed Scraper (Phase 2) ---")
    print("This script reads a list of Q-numbers and fetches detailed data for each.\n")
    
    input_file = input("Enter the input filename from Phase 1 (e.g., related_entities/Q615.txt): ").strip()
    return input_file

def read_q_numbers(filename):
    """Reads a list of Q-numbers from a text file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            q_numbers = [line.strip() for line in f if line.strip().startswith('Q')]
        print(f"✅ Successfully read {len(q_numbers)} Q-numbers from '{filename}'.")
        return q_numbers
    except FileNotFoundError:
        print(f"❌ Error: The file '{filename}' was not found.")
        sys.exit(1)

def fetch_entity_data_in_batches(q_numbers):
    """
    Fetches data for a list of Q-numbers by making batched API requests.
    Wikidata allows up to 50 IDs per request.
    """
    all_entity_data = {}
    batch_size = 50 

    for i in range(0, len(q_numbers), batch_size):
        batch = q_numbers[i:i + batch_size]
        print(f"🚀 Fetching batch {i//batch_size + 1}/{(len(q_numbers) - 1)//batch_size + 1}... (items {i+1} to {i+len(batch)})")
        
        params = {
            'action': 'wbgetentities',
            'ids': '|'.join(batch),
            'format': 'json',
            'props': 'labels|descriptions|claims'
        }
        
        try:
            response = requests.get(API_ENDPOINT, params=params, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
            if 'entities' in data:
                all_entity_data.update(data['entities'])
            time.sleep(1) # Be a good citizen
        except requests.exceptions.RequestException as e:
            print(f"❌ An error occurred during API request for batch starting at item {i+1}: {e}")
            
    return all_entity_data

def save_data_to_json(data, filename):
    """Saves the processed data to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"\n✅ Successfully saved detailed data for {len(data)} entities to '{filename}'.")
        print("This file forms the basis of your knowledge graph.")
    except IOError as e:
        print(f"❌ Error writing to file '{filename}': {e}")

def main():
    """Main function to orchestrate the script's workflow."""
    try:
        # Step 1: Get the input file path from the user
        input_file = get_user_input()
        
        # Step 2: Define the output directory and create it if it doesn't exist
        output_dir = "WikiDataScrap/detailed_info"
        if not os.path.exists(output_dir):
            print(f"Directory '{output_dir}' not found. Creating it...")
            os.makedirs(output_dir)
            
        # Step 3: Automatically generate the output file path based on the input file name
        base_name = os.path.basename(input_file)       # e.g., "Q615.txt"
        q_id_name = os.path.splitext(base_name)[0]      # e.g., "Q615"
        output_file = os.path.join(output_dir, f"{q_id_name}.json") # e.g., "detailed_info/Q615.json"

        # Step 4: Read the Q-numbers from the input file
        q_numbers = read_q_numbers(input_file)
        if not q_numbers:
            print("No Q-numbers to process. Exiting.")
            return

        # Step 5: Fetch the entity data from the API
        all_data = fetch_entity_data_in_batches(q_numbers)
        
        # Step 6: Save the data to the automatically generated file path
        if all_data:
            save_data_to_json(all_data, output_file)
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting.")
        sys.exit(0)

if __name__ == "__main__":
    main()