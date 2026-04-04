import json
import os
import subprocess
from notifier import send_job_alert
from utils import generate_fingerprint, load_processed_fingerprints, save_fingerprint

# Paths
PROCESSED_FILE = "processed_jobs.json"
JOBS_FILE = "jobs_with_descriptions.json"

def load_processed_jobs():
    """Returns a list of URLs that have already been handled."""
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_processed_job(job_url):
    """Appends a single URL string to the history file."""
    processed = load_processed_jobs()
    if job_url not in processed:
        processed.append(job_url)
        with open(PROCESSED_FILE, 'w') as f:
            json.dump(processed, f, indent=4)

def run_agent():
    print("🚀 Starting Sniper Cycle...")
    
    # 1. Run Scraper and Fetcher (Phase 1 & 2)
    # Assuming these are set up to run as standalone scripts
    subprocess.run(["python", "scraper.py"])
    subprocess.run(["python", "fetch_descriptions.py"])

    with open(JOBS_FILE, 'r') as f:
        jobs = json.load(f)

    processed_urls = load_processed_jobs()

    for job in jobs:
        # Extra safety check
        processed = load_processed_fingerprints()
        fingerprint = job.get('fingerprint') or generate_fingerprint(job['title'], job['company'])

        if fingerprint not in processed:
            try:
                # 2. Tailor Resume/CL
                subprocess.run(["python", "agent.py", job['url']], check=True)
                
                # Format file label like your current agent does
                file_label = job['company'].split()[0].replace(",", "").replace(".", "")
                pdf_path = f"Resume_Schmidt_{file_label}.pdf"
                cl_path = f"CL_Schmidt_{file_label}.txt"

                # 3. Notify via Telegram
                send_job_alert(job['title'], job['company'], job['url'], pdf_path, cl_path)
                
                # 4. SAVE FINGERPRINT ONLY AFTER SUCCESS
                save_fingerprint(fingerprint)
                print(f"✅ Successfully archived: {fingerprint}")
                
            except Exception as e:
                print(f"❌ Error tailoring {job['company']}: {e}")

if __name__ == "__main__":
    run_agent()
