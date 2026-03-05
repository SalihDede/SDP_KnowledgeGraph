import json
import sys

with open(sys.argv[1], 'r', encoding='utf-8') as f:
    data = json.load(f)
    print(len(data))