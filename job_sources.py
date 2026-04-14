import json
import os
import re
from abc import ABC, abstractmethod
from typing import Dict, Iterable, List, Sequence

from utils import generate_fingerprint

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_path(filename: str) -> str:
    return os.path.join(BASE_DIR, filename)


load_dotenv(get_path(".env"))


class JobSource(ABC):
    source_name: str

    @abstractmethod
    def scrape_jobs(self, processed_fingerprints: set[str]) -> List[dict]:
        """Return newly discovered jobs from this source."""

    @abstractmethod
    def enrich_jobs(self, jobs: Sequence[dict]) -> List[dict]:
        """Populate description fields for jobs from this source."""

    def supports_job(self, job: dict) -> bool:
        return job.get("source") == self.source_name


class SymplicitySource(JobSource):
    source_name = "symplicity"

    def __init__(self) -> None:
        self.username = os.getenv("TRU_USERNAME")
        self.password = os.getenv("TRU_PASSWORD")
        self.login_url = "https://tru-csm.symplicity.com/students/"
        self.discover_url = "https://tru-csm.symplicity.com/students/app/jobs/discover"

    def _login(self, page) -> bool:
        print("Logging into TRU Symplicity...")
        page.goto(self.login_url)

        try:
            if self.username:
                page.fill("input[name='username']", self.username)
            if self.password:
                page.fill("input[name='password']", self.password)
            page.click("input[type='submit']")
            page.wait_for_timeout(3000)
            return True
        except Exception as exc:
            print(f"   [!] Login error: {exc}")
            return False

    def scrape_jobs(self, processed_fingerprints: set[str]) -> List[dict]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, slow_mo=10)
            context = browser.new_context()
            page = context.new_page()

            self._login(page)

            print("Navigating to the Job Discovery board...")
            page.goto(self.discover_url)
            page.wait_for_load_state("networkidle")

            print("Opening 'More Filters'...")
            page.locator("button#cfEmployersAdvFiltersBtn").click()
            page.wait_for_timeout(1000)

            print("Selecting Desired Majors...")
            trigger = page.locator("div.picklist-selected-text, .picklist-field").first
            trigger.click()

            major_input = page.locator("input[placeholder='Search']").first
            major_input.wait_for(state="visible", timeout=5000)

            print("   -> Searching for 'engineering' programs...")
            major_input.fill("engineering")
            page.wait_for_timeout(2000)

            target_majors = [
                "Bachelor of Engineering",
                "BEng - Software Engineering",
                "BEng - Computer Engineering",
                "Electrical-Computer Engineering Transfer Program- 2nd yr",
                "Engineering Transfer Program",
            ]

            for major in target_majors:
                try:
                    option = page.get_by_text(major, exact=False).last
                    if option.is_visible():
                        print(f"      + Checking: {major}")
                        option.click()
                        page.wait_for_timeout(300)
                except Exception:
                    continue

            print("Refining Filters...")
            try:
                omit_text = page.get_by_text("Omit All Majors", exact=False)
                if omit_text.is_visible():
                    omit_text.click()
            except Exception:
                pass

            print("   -> Applying all filters...")
            page.locator("button[aria-label='Apply More Filters']").click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)

            current_url = page.url
            if "perPage=" in current_url:
                new_url = re.sub(r"perPage=\d+", "perPage=200", current_url)
                print("   -> Forcing 200 results per page...")
                page.goto(new_url)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(3000)

            print("Scraping Job Cards...")
            discovered_jobs: List[dict] = []
            job_cards_locator = page.locator("div.list-item[role='link']")

            count = job_cards_locator.count()
            if count == 0:
                print("   [!] No jobs found.")
                browser.close()
                return []

            print(f"   -> Found {count} matches.")

            for index in range(count):
                try:
                    card = job_cards_locator.nth(index)
                    title = card.locator(".list-item-title span").first.inner_text().strip()
                    company = card.locator(".list-item-subtitle span").first.inner_text().strip()
                    fingerprint = generate_fingerprint(title, company)

                    card.click()
                    page.wait_for_timeout(1500)

                    discovered_jobs.append(
                        {
                            "title": title,
                            "company": company,
                            "url": page.url,
                            "fingerprint": fingerprint,
                            "source": self.source_name,
                            "already_processed": fingerprint in processed_fingerprints,
                        }
                    )

                    if "/discover" not in page.url:
                        page.go_back()
                        page.wait_for_timeout(1000)
                except Exception:
                    continue

            browser.close()
            return discovered_jobs

    def enrich_jobs(self, jobs: Sequence[dict]) -> List[dict]:
        from playwright.sync_api import sync_playwright

        enriched_jobs = [dict(job) for job in jobs]
        if not enriched_jobs:
            return enriched_jobs

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            if not self._login(page):
                browser.close()
                return self._mark_manual_review(enriched_jobs, "Login failed for Symplicity.")

            for job in enriched_jobs:
                print(f"Fetching: {job['title']}...")
                try:
                    page.goto(job["url"], wait_until="networkidle", timeout=60000)
                    selector = ".field-widget-tinymce"
                    page.wait_for_selector(selector, timeout=10000)
                    description = page.locator(selector).inner_text().strip()
                    job["full_description"] = description
                    print("   [✓] Description saved.")
                except Exception:
                    job["full_description"] = "Manual review required: Selector not found."
                    print(f"   [!] Failed: {job['title']}")

            browser.close()
            return enriched_jobs

    def _mark_manual_review(self, jobs: Sequence[dict], reason: str) -> List[dict]:
        marked_jobs = []
        for job in jobs:
            updated_job = dict(job)
            updated_job["full_description"] = f"Manual review required: {reason}"
            marked_jobs.append(updated_job)
        return marked_jobs


SOURCE_REGISTRY: Dict[str, JobSource] = {
    SymplicitySource.source_name: SymplicitySource(),
}


def list_source_names() -> List[str]:
    return sorted(SOURCE_REGISTRY.keys())


def resolve_sources(requested_sources: Iterable[str] | None = None) -> List[JobSource]:
    if requested_sources is None:
        return [SOURCE_REGISTRY[name] for name in list_source_names()]

    normalized = [source.strip().lower() for source in requested_sources if source.strip()]
    if not normalized:
        return [SOURCE_REGISTRY[name] for name in list_source_names()]

    unknown = [name for name in normalized if name not in SOURCE_REGISTRY]
    if unknown:
        known = ", ".join(list_source_names())
        raise ValueError(f"Unknown job source(s): {', '.join(unknown)}. Known sources: {known}")

    return [SOURCE_REGISTRY[name] for name in normalized]


def resolve_source_for_job(job: dict) -> JobSource:
    source_name = (job.get("source") or SymplicitySource.source_name).strip().lower()
    if source_name not in SOURCE_REGISTRY:
        raise ValueError(f"Unsupported job source for job '{job.get('title', 'unknown')}': {source_name}")
    return SOURCE_REGISTRY[source_name]


def group_jobs_by_source(jobs: Sequence[dict]) -> Dict[str, List[dict]]:
    grouped: Dict[str, List[dict]] = {}
    for job in jobs:
        source_name = (job.get("source") or SymplicitySource.source_name).strip().lower()
        grouped.setdefault(source_name, []).append(job)
    return grouped


def write_jobs(filepath: str, jobs: Sequence[dict]) -> None:
    with open(filepath, "w") as file_handle:
        json.dump(list(jobs), file_handle, indent=4)
