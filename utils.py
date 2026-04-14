import os
import json
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_FILE = os.path.join(BASE_DIR, "processed_jobs.json")

def generate_fingerprint(title, company):
    """
    Creates a unique, platform-independent ID.
    Normalizes 'BenchSci (Toronto, ON)' -> 'benchsci'
    """
    # 1. Clean company: take part before '(' or '-' and remove non-alphanumeric
    clean_company = re.split(r'\(|-', company)[0].strip().lower()
    clean_company = re.sub(r'[^a-z0-9]', '', clean_company)
    
    # 2. Clean title: lowercase and alphanumeric only
    clean_title = title.lower().strip()
    clean_title = re.sub(r'[^a-z0-9]', '', clean_title)
    
    return f"{clean_company}:{clean_title}"

def load_processed_fingerprints():
    """Loads the archive of handled jobs as a set for fast lookup."""
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f:
            try:
                data = json.load(f)
                return set(data) if isinstance(data, list) else set()
            except (json.JSONDecodeError, TypeError):
                return set()
    return set()

def save_fingerprint(fingerprint):
    """Adds a new fingerprint to the archive."""
    fingerprints = load_processed_fingerprints()
    fingerprints.add(fingerprint)
    with open(PROCESSED_FILE, 'w') as f:
        # Save as a list so JSON can handle it
        json.dump(list(fingerprints), f, indent=4)
