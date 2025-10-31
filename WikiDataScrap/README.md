WIKIDATA KNOWLEDGE GRAPH DATA EXTRACTOR

This project provides a set of Python scripts designed to extract structured entity and relationship data from Wikidata.
The main goal is to collect and format data suitable for constructing a knowledge graph.

PROJECT STRUCTURE

WikiDataScrap/
│
├── json_outputs/ # Output of triple_creator.py
│ ├── Q615_triples.json
│ └── ...
│
├── detailed_info_turkish/ # Output of api_scrap_turkish.py
│ ├── Q615.json
│ └── ...
│
├── related_entities/ # Output of query.py
│ └── ...
│
├── triple_creator.py # (RECOMMENDED) Main script to extract structured triples
├── query.py # Legacy Phase 1: Finds related entity Q-IDs
├── api_scrap_turkish.py # Legacy Phase 2: Scrapes details for Q-IDs from Phase 1
│
├── api_scrap.py # 
└── create_KG.py # 

OVERVIEW OF SCRIPTS
triple_creator.py (RECOMMENDED)

A consolidated and modern script that performs the entire extraction process in a single step.
It retrieves structured relationship triples (source–relation–target) and includes type information for each entity.

Input: A single Wikidata Q-ID (e.g., Q125582 for Lionel Messi)
Output: JSON file in the json_outputs/ folder (e.g., Q125582_triples.json)

Legacy Two-Phase Approach

query.py (Phase 1)
Purpose: Finds entities related to a given Wikidata Q-ID.
Output: A .txt file (e.g., Q615.txt) saved in the related_entities/ folder.

api_scrap_turkish.py (Phase 2)
Purpose: Uses the list of Q-IDs from Phase 1 and fetches their details via the Wikidata MediaWiki API.
Output: A .json file (e.g., Q615.json) saved in the detailed_info_turkish/ folder.

SETUP INSTRUCTIONS

Prerequisites:

Python 3 installed

requests library

Installation:
Clone this repository or save the scripts locally, then install dependencies:

pip install requests

USAGE

For most use cases, it is recommended to use the triple_creator.py script.

Open your terminal or command prompt.

Navigate to the WikiDataScrap directory.

Run the script:

python triple_creator.py

When prompted, enter the Wikidata Q-ID of the entity you want to extract, for example:

--- Wikidata Relationship Triple Extractor ---
Enter the entity's Q-ID (e.g., Q125582): Q45756

The script will fetch data and save the results as a JSON file in the json_outputs/ folder,
e.g. Q45756_triples.json.

OUTPUT FORMAT

Each JSON file contains a list of relationship triples in the following format:

[
{
"baş": "Thierry Henry",
"baş_tipi": "insan",
"ilişki": "üyelik",
"uç": "Fransa millî futbol takımı",
"uç_tipi": "millî futbol takımı"
},
{
"baş": "Thierry Henry",
"baş_tipi": "insan",
"ilişki": "çalıştığı takım",
"uç": "FC Barcelona",
"uç_tipi": "futbol kulübü"
}
]

Field Descriptions:
baş → Label of the source entity
baş_tipi → “Instance of” (P31) type for the source entity
ilişki → Label of the property connecting the two entities
uç → Label of the target (object) entity
uç_tipi → “Instance of” (P31) type for the target entity

CUSTOMIZATION

You can add manual translations for missing Turkish labels directly inside triple_creator.py.
Edit the translation_map dictionary inside the process_and_save_results() function:

Add any English terms you find and their Turkish translations here.

translation_map = {
"sports award": "spor ödülü",
"human": "insan",
# Add more mappings here:
"english label": "türkçe karşılığı"
}