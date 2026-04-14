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
        write_jobs(OUTPUT_FILE, [])
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

    write_jobs(OUTPUT_FILE, enriched_jobs)
    print(f"\nDone! Processed {len(enriched_jobs)} jobs.")
    return enriched_jobs


if __name__ == "__main__":
    fetch_details(sys.argv[1:])
