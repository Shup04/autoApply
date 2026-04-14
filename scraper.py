import sys

from job_sources import get_path, resolve_sources, write_jobs
from utils import load_processed_fingerprints

OUTPUT_FILE = get_path("scraped_jobs.json")


def scrape_jobs(source_names=None):
    processed_fingerprints = load_processed_fingerprints()
    all_jobs = []
    new_job_count = 0

    for source in resolve_sources(source_names):
        print(f"Scraping source: {source.source_name}")
        source_jobs = source.scrape_jobs(processed_fingerprints)
        new_job_count += sum(1 for job in source_jobs if not job.get("already_processed"))
        all_jobs.extend(source_jobs)

    write_jobs(OUTPUT_FILE, all_jobs)
    print(
        f"\nSuccess! Saved {len(all_jobs)} jobs "
        f"({new_job_count} new, {len(all_jobs) - new_job_count} already processed)."
    )
    return all_jobs


def scrape_symplicity_jobs():
    return scrape_jobs(["symplicity"])


if __name__ == "__main__":
    scrape_jobs(sys.argv[1:])
