import os
import sys
import glob
from mainScrapWiki import derin_scrap

def verify_logging():
    # Test parameters
    root_url = "https://tr.wikipedia.org/wiki/Python_(programlama_dili)"
    max_depth = 0
    
    print(f"Testing with URL: {root_url} and Depth: {max_depth}")
    
    # Run the scraper
    try:
        derin_scrap(root_url, max_depth=max_depth, bekleme_suresi=1, paralel_worker=2)
    except Exception as e:
        print(f"Error running scraper: {e}")
        return

    # Find the output folder
    # The script changes directory to the output folder, so we should be in it?
    # No, derin_scrap changes directory, but does it change it back?
    # Yes, it does: os.chdir(original_dir) at the end.
    
    # So we need to find the created folder in the current directory
    folders = glob.glob("Scraping_*_depth0")
    if not folders:
        print("Error: Output folder not found.")
        return
    
    latest_folder = max(folders, key=os.path.getctime)
    print(f"Checking folder: {latest_folder}")
    
    # Check for run log file
    log_files = glob.glob(os.path.join(latest_folder, "Run_Log_*.txt"))
    if not log_files:
        print("Error: Run log file not found.")
        return
        
    log_file = log_files[0]
    print(f"Found log file: {log_file}")
    
    # Read and verify content
    with open(log_file, "r", encoding="utf-8") as f:
        content = f.read()
        
    print("\nLog Content Preview:")
    print("-" * 20)
    print(content)
    print("-" * 20)
    
    required_strings = [
        "Run Log:",
        "Depth: 0",
        "Scraped Pages (Success):",
        "Unique URL-Entity Pairs:",
        "Time:",
        "Success:",
        "Failed:",
        "Skipped:"
    ]
    
    missing = [s for s in required_strings if s not in content]
    
    if missing:
        print(f"FAILED: Missing required log entries: {missing}")
    else:
        print("SUCCESS: All required log entries found.")

if __name__ == "__main__":
    verify_logging()
