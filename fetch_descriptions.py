import os
import sys
import json

from job_sources import (
    get_path,
    group_jobs_by_source,
    resolve_source_for_job,
    resolve_sources,
    write_jobs,
)

INPUT_FILE = get_path("scraped_jobs.json")
OUTPUT_FILE = get_path("jobs_with_descriptions.json")


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
        key = job.get("fingerprint") or job.get("url")
        if key:
            merged_by_key[key] = job

    for job in new_jobs:
        key = job.get("fingerprint") or job.get("url")
        if key:
            previous = merged_by_key.get(key, {})
            merged_by_key[key] = {**previous, **job}

    return list(merged_by_key.values())


def fetch_details(source_names=None):
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return []

    with open(INPUT_FILE, "r") as file_handle:
        jobs = json.load(file_handle)

    if source_names:
        allowed_sources = {source.source_name for source in resolve_sources(source_names)}
        jobs = [job for job in jobs if (job.get("source") or "symplicity").lower() in allowed_sources]

    if not jobs:
        print("No new jobs to fetch descriptions for.")
        existing_jobs = load_existing_jobs()
        write_jobs(OUTPUT_FILE, existing_jobs)
        return []

    enriched_jobs = []
    for source_name, source_jobs in group_jobs_by_source(jobs).items():
        print(f"Fetching descriptions from source: {source_name}")
        try:
            source = resolve_source_for_job(source_jobs[0])
            enriched_jobs.extend(source.enrich_jobs(source_jobs))
        except ValueError as exc:
            print(f"   [!] {exc}")
            for job in source_jobs:
                updated_job = dict(job)
                updated_job["full_description"] = "Manual review required: Unsupported job source."
                enriched_jobs.append(updated_job)

    existing_jobs = load_existing_jobs()
    existing_count = len(existing_jobs)
    all_jobs = merge_jobs(existing_jobs, enriched_jobs)
    total_added = len(all_jobs) - existing_count

    write_jobs(OUTPUT_FILE, all_jobs)
    print(
        f"\nDone! Processed {len(enriched_jobs)} jobs. "
        f"`{OUTPUT_FILE}` now contains {len(all_jobs)} total jobs ({total_added:+d} net change)."
    )
    return all_jobs


if __name__ == "__main__":
    fetch_details(sys.argv[1:])
