import json
import os
import sys
import subprocess
from notifier import send_job_alert
from utils import (
    backfill_application_job_ids,
    build_job_artifact_label,
    generate_fingerprint,
    load_processed_fingerprints,
    save_fingerprint,
    upsert_application_record,
)

# --- PATH LOGIC ---
# This finds the absolute path of the directory containing main.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_DIR, filename)

PROCESSED_FILE = get_path("processed_jobs.json")
JOBS_FILE = get_path("jobs_with_descriptions.json")
# ------------------

def load_processed_jobs():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_processed_job(job_url):
    processed = load_processed_jobs()
    if job_url not in processed:
        processed.append(job_url)
        with open(PROCESSED_FILE, 'w') as f:
            json.dump(processed, f, indent=4)

def run_agent(source_names=None):
    backfill_application_job_ids()
    try:
        print("🚀 Starting Sniper Cycle...")
        source_args = list(source_names or [])

        print("Scraping Jobs...")
        subprocess.run([sys.executable, get_path("scraper.py"), *source_args], check=True)

        print("Fetching Descriptions...")
        subprocess.run([sys.executable, get_path("fetch_descriptions.py"), *source_args], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Subprocess failed! Logic error in scraper or fetcher: {e}")
        return 

    # Ensure we open the absolute path of the jobs file
    if not os.path.exists(JOBS_FILE):
        print(f"⚠️ {JOBS_FILE} not found. Scraper might have failed silently.")
        return

    with open(JOBS_FILE, 'r') as f:
        jobs = json.load(f)

    for job in jobs:
        # Note: Ensure load_processed_fingerprints() in utils.py also uses absolute paths!
        processed = load_processed_fingerprints()
        fingerprint = job.get('fingerprint') or generate_fingerprint(job['title'], job['company'])

        if fingerprint not in processed:
            try:
                print(f"✨ Processing: {job['title']} @ {job['company']}")
                # Absolute path for agent.py as well
                subprocess.run([sys.executable, get_path("agent.py"), job['url']], check=True)
                
                file_label = build_job_artifact_label(job["company"], job["title"])
                
                # Use get_path for output directories too
                pdf_path = get_path(os.path.join("resumes", f"Resume_Schmidt_{file_label}.pdf"))
                cl_path = get_path(os.path.join("cover_letters", f"CL_Schmidt_{file_label}.pdf"))

                record = upsert_application_record(
                    job,
                    "prepared",
                    artifact_label=file_label,
                    resume_path=pdf_path,
                    cover_letter_path=cl_path,
                )
                message_ids = send_job_alert(
                    record["job_id"],
                    job['title'],
                    job['company'],
                    job['url'],
                    pdf_path,
                    cl_path,
                )
                upsert_application_record(
                    job,
                    "prepared",
                    artifact_label=file_label,
                    resume_path=pdf_path,
                    cover_letter_path=cl_path,
                    telegram_message_ids=message_ids,
                )
                
                save_fingerprint(fingerprint)
                print(f"✅ Successfully archived: {fingerprint}")
                
            except Exception as e:
                print(f"❌ Error tailoring {job['company']}: {e}")

if __name__ == "__main__":
    run_agent(sys.argv[1:])
