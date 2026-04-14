import sys
import json
import os

from job_sources import get_path, resolve_sources, write_jobs
from utils import load_processed_fingerprints

OUTPUT_FILE = get_path("scraped_jobs.json")


def load_existing_jobs():
    if not os.path.exists(OUTPUT_FILE):
        return []

    try:
        with open(OUTPUT_FILE, "r") as file_handle:
            data = json.load(file_handle)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def merge_jobs(existing_jobs, new_jobs):
    merged_by_key = {}

    for job in existing_jobs:
        key = job.get("url") or job.get("fingerprint")
        if key:
            merged_by_key[key] = job

    for job in new_jobs:
        key = job.get("url") or job.get("fingerprint")
        if key:
            merged_by_key[key] = job

    return list(merged_by_key.values())


def scrape_jobs(source_names=None):
    processed_fingerprints = load_processed_fingerprints()
    scraped_jobs = []
    new_job_count = 0

    for source in resolve_sources(source_names):
        print(f"Scraping source: {source.source_name}")
        source_jobs = source.scrape_jobs(processed_fingerprints)
        new_job_count += sum(1 for job in source_jobs if not job.get("already_processed"))
        scraped_jobs.extend(source_jobs)

    existing_jobs = load_existing_jobs()
    existing_count = len(existing_jobs)
    all_jobs = merge_jobs(existing_jobs, scraped_jobs)
    total_added = len(all_jobs) - existing_count
    write_jobs(OUTPUT_FILE, all_jobs)
    print(
        f"\nSuccess! {len(scraped_jobs)} jobs scraped this run, "
        f"{new_job_count} new and {len(scraped_jobs) - new_job_count} already processed. "
        f"`{OUTPUT_FILE}` now contains {len(all_jobs)} total jobs "
        f"({total_added:+d} net change)."
    )
    return all_jobs


def scrape_symplicity_jobs():
    return scrape_jobs(["symplicity"])


if __name__ == "__main__":
    scrape_jobs(sys.argv[1:])
