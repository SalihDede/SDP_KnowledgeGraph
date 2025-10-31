#!/usr/bin/env python3

"""
Phase 2: Detailed Data Scraper with the API (Automated & Turkish-Focused)
"""

import requests
import sys
import json
import time
import os

API_ENDPOINT = "https://www.wikidata.org/w/api.php"
HEADERS = {'User-Agent': 'MyKnowledgeGraphProject/1.0 (contact@example.com)'}

def get_user_input():
    """Prompts the user for the input filename."""
    print("--- Wikidata Detailed Scraper (Phase 2 - Turkish) ---")
    input_file = input("Enter the input filename from Phase 1 (e.g., related_entities/Q615.txt): ").strip()
    return input_file

def read_q_numbers(filename):
    """Reads Q-numbers from a text file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            q_numbers = [line.strip() for line in f if line.strip().startswith('Q')]
        print(f"✅ Successfully read {len(q_numbers)} Q-numbers from '{filename}'.")
        return q_numbers
    except FileNotFoundError:
        print(f"❌ Error: The file '{filename}' was not found.")
        sys.exit(1)

def fetch_entity_data_in_batches(q_numbers):
    """Fetches full entity data in batches of 50."""
    all_entity_data = {}
    batch_size = 50
    for i in range(0, len(q_numbers), batch_size):
        batch = q_numbers[i:i + batch_size]
        print(f"🚀 Fetching batch {i//batch_size + 1}/{(len(q_numbers) - 1)//batch_size + 1}...")
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
            time.sleep(1)
        except requests.exceptions.RequestException as e:
            print(f"❌ API request error for batch starting at item {i+1}: {e}")
    return all_entity_data

def process_and_save_turkish_data(data, filename):
    """
    Processes the raw API response to extract Turkish-specific info and saves it.
    """
    processed_results = {}
    for q_id, entity_data in data.items():
        # Get Turkish label, fallback to English label, then to the Q-ID
        label = entity_data.get('labels', {}).get('tr', {}).get('value')
        if not label:
            label = entity_data.get('labels', {}).get('en', {}).get('value', q_id)
            
        # Get Turkish description, fallback to English
        description = entity_data.get('descriptions', {}).get('tr', {}).get('value')
        if not description:
            description = entity_data.get('descriptions', {}).get('en', {}).get('value', 'No description available.')
            
        processed_results[q_id] = {
            'id': q_id,
            'label_tr': label,
            'description_tr': description,
            'claims': entity_data.get('claims', {})
        }

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(processed_results, f, indent=4, ensure_ascii=False)
        print(f"\n✅ Successfully saved Turkish-focused data for {len(processed_results)} entities to '{filename}'.")
    except IOError as e:
        print(f"❌ Error writing to file '{filename}': {e}")

def main():
    """Main function to orchestrate the script."""
    try:
        input_file = get_user_input()
        
        output_dir = "WikiDataScrap/detailed_info_turkish" # Save to a new folder
        if not os.path.exists(output_dir):
            print(f"Directory '{output_dir}' not found. Creating it...")
            os.makedirs(output_dir)
            
        base_name = os.path.basename(input_file)
        q_id_name = os.path.splitext(base_name)[0]
        output_file = os.path.join(output_dir, f"{q_id_name}.json")

        q_numbers = read_q_numbers(input_file)
        if not q_numbers:
            return

        all_data = fetch_entity_data_in_batches(q_numbers)
        if all_data:
            process_and_save_turkish_data(all_data, output_file)
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting.")
        sys.exit(0)

if __name__ == "__main__":
    main()