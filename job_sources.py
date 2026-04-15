import json
import os
import re
from abc import ABC, abstractmethod
from typing import Dict, Iterable, List, Sequence
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from utils import generate_fingerprint, is_software_coop_role

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
                    if not is_software_coop_role(title):
                        continue
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


class LinkedInSource(JobSource):
    source_name = "linkedin"

    def __init__(self) -> None:
        self.search_terms = self._load_list(
            "LINKEDIN_SEARCH_TERMS",
            [
                "software engineer intern",
                "software engineer co-op",
                "software developer intern",
                "software developer co-op",
            ],
        )
        self.locations = self._load_list(
            "LINKEDIN_LOCATIONS",
            [
                "British Columbia, Canada",
                "Alberta, Canada",
            ],
        )
        self.allowed_location_terms = (
            "canada",
            "british columbia",
            "alberta",
            "bc",
            "ab",
            "vancouver",
            "burnaby",
            "victoria",
            "kelowna",
            "kamloops",
            "surrey",
            "calgary",
            "edmonton",
            "remote - canada",
            "canada remote",
            "remote, canada",
            "remote in canada",
        )
        self.us_location_terms = (
            "united states",
            "u.s.",
            "washington, united states",
            "california",
            "massachusetts",
            "north carolina",
            "texas",
            "new york",
            "illinois",
            "seattle",
            "boston",
            "pleasanton",
            "durham, nc",
            "north reading",
                "marlborough",
        )
        self.max_results_per_search = self._load_int("LINKEDIN_MAX_RESULTS_PER_SEARCH", 15)
        self.max_pages_per_search = self._load_int("LINKEDIN_MAX_PAGES_PER_SEARCH", 1)
        self.request_delay_ms = self._load_int("LINKEDIN_REQUEST_DELAY_MS", 4000)

    def _load_list(self, env_name: str, default: Sequence[str]) -> List[str]:
        raw = os.getenv(env_name, "")
        if not raw.strip():
            return list(default)
        values = [self._normalize_location_or_term(item.strip()) for item in raw.split("|") if item.strip()]
        deduped = list(dict.fromkeys(values))
        return deduped or list(default)

    def _normalize_location_or_term(self, value: str) -> str:
        normalized = value.strip()
        aliases = {
            "bc": "British Columbia, Canada",
            "british columbia": "British Columbia, Canada",
            "alberta": "Alberta, Canada",
            "ab": "Alberta, Canada",
        }
        return aliases.get(normalized.lower(), normalized)

    def _load_int(self, env_name: str, default: int) -> int:
        try:
            return int(os.getenv(env_name, default))
        except (TypeError, ValueError):
            return default

    def _pause(self, page, minimum_ms: int | None = None) -> None:
        delay_ms = max(self.request_delay_ms, minimum_ms or 0)
        if delay_ms > 0:
            page.wait_for_timeout(delay_ms)

    def _build_search_url(self, keywords: str, location: str, start: int = 0) -> str:
        params = {
            "keywords": keywords,
            "location": location,
            "f_TPR": "r604800",  # posted in the last 7 days
            "position": "1",
            "pageNum": str((start // 25) + 1),
            "start": str(start),
        }
        return "https://www.linkedin.com/jobs/search/?" + "&".join(
            f"{key}={quote_plus(value)}" for key, value in params.items()
        )

    def _extract_company(self, card) -> str:
        selectors = [
            ".base-search-card__subtitle",
            ".artdeco-entity-lockup__subtitle",
            "h4",
        ]
        for selector in selectors:
            try:
                text = card.locator(selector).first.inner_text().strip()
                if text:
                    return text
            except Exception:
                continue
        return "Unknown Company"

    def _extract_location(self, card) -> str:
        selectors = [
            ".job-search-card__location",
            ".job-search-card__listdate",
            ".artdeco-entity-lockup__caption",
        ]
        for selector in selectors:
            try:
                text = card.locator(selector).first.inner_text().strip()
                if text:
                    return text
            except Exception:
                continue
        return ""

    def _extract_job_url(self, card):
        selectors = [
            "a.base-card__full-link",
            "a[href*='/jobs/view/']",
            "a",
        ]
        for selector in selectors:
            try:
                href = card.locator(selector).first.get_attribute("href")
                if href:
                    return href.split("?")[0]
            except Exception:
                continue
        return None

    def _extract_title(self, card) -> str:
        selectors = [
            "h3.base-search-card__title",
            ".base-search-card__title",
            "h3",
        ]
        for selector in selectors:
            try:
                text = card.locator(selector).first.inner_text().strip()
                if text:
                    return " ".join(text.split())
            except Exception:
                continue
        return ""

    def _matches_target_role(self, title: str) -> bool:
        return is_software_coop_role(title)

    def _matches_location(self, location: str) -> bool:
        normalized = " ".join(location.lower().split())
        has_allowed = any(term in normalized for term in self.allowed_location_terms)
        has_us_marker = any(term in normalized for term in self.us_location_terms) or bool(
            re.search(r",\s*(wa|ca|ma|nc|tx|ny|il)\b", normalized)
        )
        return has_allowed and not has_us_marker

    def scrape_jobs(self, processed_fingerprints: set[str]) -> List[dict]:
        from playwright.sync_api import sync_playwright

        discovered_by_url: Dict[str, dict] = {}
        cards_inspected = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, slow_mo=20)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            print("Using public LinkedIn job pages only; login is disabled.")

            for keywords in self.search_terms:
                for location in self.locations:
                    for page_index in range(self.max_pages_per_search):
                        start = page_index * 25
                        print(f"Searching LinkedIn: {keywords} | {location} | start={start}")
                        try:
                            page.goto(
                                self._build_search_url(keywords, location, start=start),
                                wait_until="domcontentloaded",
                                timeout=60000,
                            )
                            self._pause(page, minimum_ms=3000)
                        except Exception as exc:
                            print(f"   [!] Search failed: {exc}")
                            continue

                        card_locator = page.locator("li:has(a[href*='/jobs/view/'])")
                        count = min(card_locator.count(), self.max_results_per_search)
                        if count == 0:
                            if page_index == 0:
                                print("   [!] No LinkedIn cards found for this search.")
                            break

                        print(f"   -> Found {count} LinkedIn cards to inspect.")
                        added_this_page = 0
                        cards_inspected += count
                        for index in range(count):
                            try:
                                card = card_locator.nth(index)
                                title = self._extract_title(card)
                                if not title or not self._matches_target_role(title):
                                    continue

                                company = self._extract_company(card)
                                job_url = self._extract_job_url(card)
                                if not job_url:
                                    continue

                                location_text = self._extract_location(card) or location
                                if location_text and not self._matches_location(location_text):
                                    continue
                                fingerprint = generate_fingerprint(title, company)
                                if job_url not in discovered_by_url:
                                    discovered_by_url[job_url] = {
                                        "title": title,
                                        "company": company,
                                        "location": location_text,
                                        "url": job_url,
                                        "fingerprint": fingerprint,
                                        "source": self.source_name,
                                        "search_keywords": keywords,
                                        "already_processed": fingerprint in processed_fingerprints,
                                    }
                                    added_this_page += 1
                            except Exception:
                                continue

                        if added_this_page == 0 and page_index > 0:
                            break

            browser.close()

        print(
            f"LinkedIn scrape summary: inspected about {cards_inspected} cards, "
            f"kept {len(discovered_by_url)} unique jobs."
        )
        return list(discovered_by_url.values())

    def enrich_jobs(self, jobs: Sequence[dict]) -> List[dict]:
        from playwright.sync_api import sync_playwright

        enriched_jobs = [dict(job) for job in jobs]
        if not enriched_jobs:
            return enriched_jobs

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            for job in enriched_jobs:
                print(f"Fetching: {job['title']}...")
                try:
                    page.goto(job["url"], wait_until="domcontentloaded", timeout=60000)
                    self._pause(page, minimum_ms=3000)
                    selectors = [
                        ".show-more-less-html__markup",
                        ".jobs-description__content",
                        ".description__text",
                    ]

                    description = ""
                    for selector in selectors:
                        try:
                            page.wait_for_selector(selector, timeout=5000)
                            description = page.locator(selector).first.inner_text().strip()
                            if description:
                                break
                        except Exception:
                            continue

                    if description:
                        job["full_description"] = description
                        print("   [✓] Description saved.")
                    else:
                        job["full_description"] = (
                            "Manual review required: LinkedIn description not available from public page."
                        )
                        print(f"   [!] Failed: {job['title']}")
                except Exception:
                    job["full_description"] = "Manual review required: LinkedIn page fetch failed."
                    print(f"   [!] Failed: {job['title']}")

            browser.close()
            return enriched_jobs


class JobBankSource(JobSource):
    source_name = "jobbank"

    def __init__(self) -> None:
        self.search_terms = self._load_list(
            "JOBBANK_SEARCH_TERMS",
            [
                "software developer",
                "software engineer",
                "software engineering",
                "application developer",
                "web developer",
            ],
        )
        self.provinces = self._load_list("JOBBANK_PROVINCES", ["BC", "AB"])
        self.max_pages_per_search = self._load_int("JOBBANK_MAX_PAGES_PER_SEARCH", 3)
        self.search_url = "https://www.jobbank.gc.ca/jobsearch/jobsearch"

    def _load_list(self, env_name: str, default: Sequence[str]) -> List[str]:
        raw = os.getenv(env_name, "")
        if not raw.strip():
            return list(default)
        values = [item.strip() for item in raw.split("|") if item.strip()]
        return values or list(default)

    def _load_int(self, env_name: str, default: int) -> int:
        try:
            return int(os.getenv(env_name, default))
        except (TypeError, ValueError):
            return default

    def _build_search_url(self, keywords: str, province: str, page_num: int = 1) -> str:
        params = {
            "searchstring": keywords,
            "fprov": province,
            "sort": "D",
            "page": str(page_num),
        }
        return self.search_url + "?" + "&".join(
            f"{key}={quote_plus(value)}" for key, value in params.items()
        )

    def _extract_text(self, locator, selectors: Sequence[str]) -> str:
        for selector in selectors:
            try:
                text = locator.locator(selector).first.inner_text().strip()
                if text:
                    return " ".join(text.split())
            except Exception:
                continue
        return ""

    def _extract_attr(self, locator, selectors: Sequence[str], attr: str) -> str:
        for selector in selectors:
            try:
                value = locator.locator(selector).first.get_attribute(attr)
                if value:
                    return value.split("?")[0]
            except Exception:
                continue
        return ""

    def _matches_target_role(self, title: str) -> bool:
        return is_software_coop_role(title)

    def scrape_jobs(self, processed_fingerprints: set[str]) -> List[dict]:
        from playwright.sync_api import sync_playwright

        discovered_by_url: Dict[str, dict] = {}
        cards_inspected = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            for keywords in self.search_terms:
                for province in self.provinces:
                    for page_num in range(1, self.max_pages_per_search + 1):
                        print(f"Searching Job Bank: {keywords} | {province} | page={page_num}")
                        try:
                            page.goto(
                                self._build_search_url(keywords, province, page_num=page_num),
                                wait_until="domcontentloaded",
                                timeout=60000,
                            )
                            page.wait_for_timeout(2000)
                        except Exception as exc:
                            print(f"   [!] Search failed: {exc}")
                            continue

                        card_locator = page.locator("article, li:has(a[href*='/jobsearch/jobposting/'])")
                        count = card_locator.count()
                        if count == 0:
                            if page_num == 1:
                                print("   [!] No Job Bank cards found for this search.")
                            break

                        print(f"   -> Found {count} Job Bank cards to inspect.")
                        cards_inspected += count
                        added_this_page = 0

                        for index in range(count):
                            try:
                                card = card_locator.nth(index)
                                title = self._extract_text(
                                    card,
                                    [
                                        "h3",
                                        "h2",
                                        "a.job-title",
                                        "a[href*='/jobsearch/jobposting/']",
                                    ],
                                )
                                if not title or not self._matches_target_role(title):
                                    continue

                                company = self._extract_text(
                                    card,
                                    [
                                        ".business",
                                        ".company",
                                        "ul li",
                                        "p",
                                    ],
                                ) or "Unknown Company"
                                job_url = self._extract_attr(
                                    card,
                                    [
                                        "a[href*='/jobsearch/jobposting/']",
                                        "a",
                                    ],
                                    "href",
                                )
                                if not job_url:
                                    continue
                                if job_url.startswith("/"):
                                    job_url = f"https://www.jobbank.gc.ca{job_url}"

                                location_text = self._extract_text(
                                    card,
                                    [
                                        ".location",
                                        ".city",
                                        "li",
                                    ],
                                ) or province
                                fingerprint = generate_fingerprint(title, company)

                                if job_url not in discovered_by_url:
                                    discovered_by_url[job_url] = {
                                        "title": title,
                                        "company": company,
                                        "location": location_text,
                                        "url": job_url,
                                        "fingerprint": fingerprint,
                                        "source": self.source_name,
                                        "search_keywords": keywords,
                                        "already_processed": fingerprint in processed_fingerprints,
                                    }
                                    added_this_page += 1
                            except Exception:
                                continue

                        if added_this_page == 0 and page_num > 1:
                            break

            browser.close()

        print(
            f"Job Bank scrape summary: inspected about {cards_inspected} cards, "
            f"kept {len(discovered_by_url)} unique jobs."
        )
        return list(discovered_by_url.values())

    def enrich_jobs(self, jobs: Sequence[dict]) -> List[dict]:
        from playwright.sync_api import sync_playwright

        enriched_jobs = [dict(job) for job in jobs]
        if not enriched_jobs:
            return enriched_jobs

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            for job in enriched_jobs:
                print(f"Fetching: {job['title']}...")
                try:
                    page.goto(job["url"], wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(2000)

                    selectors = [
                        "#job-details",
                        ".job-posting-details",
                        ".jobsearch-JobComponent",
                        "main",
                    ]
                    description = ""
                    for selector in selectors:
                        try:
                            page.wait_for_selector(selector, timeout=5000)
                            description = page.locator(selector).first.inner_text().strip()
                            if description:
                                break
                        except Exception:
                            continue

                    if description:
                        job["full_description"] = description
                        print("   [✓] Description saved.")
                    else:
                        job["full_description"] = (
                            "Manual review required: Job Bank description selector not found."
                        )
                        print(f"   [!] Failed: {job['title']}")
                except Exception:
                    job["full_description"] = "Manual review required: Job Bank page fetch failed."
                    print(f"   [!] Failed: {job['title']}")

            browser.close()
            return enriched_jobs


class CompanyBoardsSource(JobSource):
    source_name = "company_boards"

    def __init__(self) -> None:
        self.config_path = get_path("company_boards.json")
        self.user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        self.role_terms = self._load_list(
            "COMPANY_BOARD_ROLE_TERMS",
            [
                "software",
                "developer",
                "engineer",
                "firmware",
                "backend",
                "frontend",
                "full stack",
                "platform",
                "application",
                "mobile",
                "machine learning",
                "ml",
                "ai",
                "embedded",
                "systems",
            ],
        )
        self.experience_terms = self._load_list(
            "COMPANY_BOARD_EXPERIENCE_TERMS",
            ["intern", "internship", "co-op", "coop", "student"],
        )
        self.allowed_location_terms = self._load_list(
            "COMPANY_BOARD_LOCATIONS",
            [
                "canada",
                "british columbia",
                "bc",
                "vancouver",
                "burnaby",
                "richmond",
                "victoria",
                "kelowna",
                "kamloops",
                "surrey",
                "alberta",
                "ab",
                "calgary",
                "edmonton",
                "remote - canada",
                "canada remote",
                "remote, canada",
            ],
        )
        self.disallowed_location_terms = self._load_list(
            "COMPANY_BOARD_DISALLOWED_LOCATIONS",
            [
                "united states",
                "usa",
                "u.s.",
                "washington, united states",
                "california",
                "massachusetts",
                "north carolina",
                "texas",
                "new york",
                "illinois",
            ],
        )
        self.excluded_title_terms = self._load_list(
            "COMPANY_BOARD_EXCLUDED_TITLE_TERMS",
            [
                "senior",
                "staff",
                "principal",
                "lead ",
                "manager",
                "director",
                "architect",
                "business development",
                "sales",
                "account executive",
                "customer success",
                "marketing",
                "finance",
                "accounting",
                "accountant",
                "hr",
                "human resources",
                "recruiter",
                "talent",
                "general applications",
                "general application",
                "talent pool",
                "artist",
                "designer",
                "payroll",
                "product manager",
                "project manager",
                "security engineer",
            ],
        )

    def _load_list(self, env_name: str, default: Sequence[str]) -> List[str]:
        raw = os.getenv(env_name, "")
        if not raw.strip():
            return list(default)
        values = [item.strip().lower() for item in raw.split("|") if item.strip()]
        return values or [item.lower() for item in default]

    def _load_config(self) -> List[dict]:
        if not os.path.exists(self.config_path):
            return []
        try:
            with open(self.config_path, "r") as file_handle:
                data = json.load(file_handle)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _fetch_json(self, url: str) -> dict | list | None:
        request = Request(url, headers={"User-Agent": self.user_agent})
        with urlopen(request, timeout=60) as response:
            return json.load(response)

    def _fetch_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": self.user_agent})
        with urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8", errors="ignore")

    def _matches_role(self, text: str) -> bool:
        normalized = text.lower()
        return any(term in normalized for term in self.role_terms)

    def _matches_experience(self, text: str) -> bool:
        normalized = text.lower()
        return any(term in normalized for term in self.experience_terms)

    def _is_excluded_title(self, title: str) -> bool:
        normalized = title.lower()
        return any(term in normalized for term in self.excluded_title_terms)

    def _matches_location(self, location: str, board: dict) -> bool:
        normalized = location.lower()
        extra_terms = [term.lower() for term in board.get("location_keywords", [])]
        allowed_terms = self.allowed_location_terms + extra_terms
        has_allowed = any(term in normalized for term in allowed_terms)
        has_disallowed = any(term in normalized for term in self.disallowed_location_terms)
        has_canadian_marker = any(
            term in normalized
            for term in ["canada", "british columbia", "alberta", "ontario", "bc", "ab"]
        )
        return has_allowed and (not has_disallowed or has_canadian_marker)

    def _make_job(
        self,
        board: dict,
        title: str,
        company: str,
        location: str,
        url: str,
        description: str,
        processed_fingerprints: set[str],
    ) -> dict:
        fingerprint = generate_fingerprint(title, company)
        return {
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "fingerprint": fingerprint,
            "source": self.source_name,
            "board_company": board.get("company", company),
            "board_type": board.get("ats", "unknown"),
            "full_description": description,
            "already_processed": fingerprint in processed_fingerprints,
        }

    def _scrape_lever_board(self, board: dict, processed_fingerprints: set[str]) -> List[dict]:
        company = board["company"]
        board_slug = board["board"]
        api_url = f"https://api.lever.co/v0/postings/{board_slug}?mode=json"
        postings = self._fetch_json(api_url) or []
        discovered = []

        for posting in postings:
            title = (posting.get("text") or "").strip()
            categories = posting.get("categories") or {}
            location = (categories.get("location") or board.get("default_location") or "").strip()
            url = (posting.get("hostedUrl") or "").strip()
            description = (posting.get("descriptionPlain") or posting.get("description") or "").strip()
            team = (categories.get("team") or "").strip()
            commitment = (categories.get("commitment") or "").strip()
            level = (categories.get("level") or "").strip()
            workplace = (categories.get("workplace") or "").strip()
            search_blob = " ".join(
                part for part in [title, team, commitment, level, workplace, description] if part
            )
            experience_blob = " ".join(part for part in [title, commitment, level, team] if part)

            if not title or not url:
                continue
            if self._is_excluded_title(title):
                continue
            if not is_software_coop_role(title, search_blob):
                continue
            if not self._matches_role(title) and not self._matches_role(search_blob):
                continue
            if not self._matches_experience(experience_blob) and not self._matches_experience(search_blob):
                continue
            if location and not self._matches_location(location, board):
                continue

            discovered.append(
                self._make_job(
                    board,
                    title,
                    company,
                    location or board.get("default_location", ""),
                    url,
                    description,
                    processed_fingerprints,
                )
            )

        return discovered

    def _scrape_greenhouse_board(self, board: dict, processed_fingerprints: set[str]) -> List[dict]:
        company = board["company"]
        board_slug = board["board"]
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_slug}/jobs?content=true"
        postings = []
        try:
            payload = self._fetch_json(api_url) or {}
            postings = payload.get("jobs", []) if isinstance(payload, dict) else []
        except Exception:
            postings = self._scrape_greenhouse_board_fallback(board)
        discovered = []

        for posting in postings:
            title = (posting.get("title") or "").strip()
            location = ((posting.get("location") or {}).get("name") or board.get("default_location") or "").strip()
            url = (posting.get("absolute_url") or "").strip()
            description = (posting.get("content") or "").strip()
            metadata_items = posting.get("metadata", []) or []
            metadata_text_parts = []
            for item in metadata_items:
                if not isinstance(item, dict):
                    continue
                value = item.get("value", "")
                if isinstance(value, str):
                    metadata_text_parts.append(value)
                elif isinstance(value, dict):
                    metadata_text_parts.extend(
                        str(nested_value)
                        for nested_value in value.values()
                        if isinstance(nested_value, (str, int, float))
                    )
            metadata_text = " ".join(metadata_text_parts)
            search_blob = " ".join(part for part in [title, metadata_text, description] if part)
            experience_blob = " ".join(part for part in [title, metadata_text] if part)

            if not title or not url:
                continue
            if self._is_excluded_title(title):
                continue
            if not is_software_coop_role(title, search_blob):
                continue
            if not self._matches_role(title) and not self._matches_role(search_blob):
                continue
            if not self._matches_experience(experience_blob) and not self._matches_experience(search_blob):
                continue
            if location and not self._matches_location(location, board):
                continue

            discovered.append(
                self._make_job(
                    board,
                    title,
                    company,
                    location or board.get("default_location", ""),
                    url,
                    description,
                    processed_fingerprints,
                )
            )

        return discovered

    def _scrape_greenhouse_board_fallback(self, board: dict) -> List[dict]:
        from playwright.sync_api import sync_playwright

        board_slug = board["board"]
        candidate_urls = [
            f"https://job-boards.greenhouse.io/{board_slug}",
            f"https://job-boards.greenhouse.io/embed/job_board?for={board_slug}",
        ]

        discovered = []
        seen_urls = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=self.user_agent)
            page = context.new_page()

            opened = False
            for candidate_url in candidate_urls:
                try:
                    page.goto(candidate_url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(1500)
                    opened = True
                    break
                except Exception:
                    continue

            if not opened:
                browser.close()
                return []

            anchors = page.locator("a[href*='/jobs/']")
            count = anchors.count()
            for index in range(count):
                try:
                    anchor = anchors.nth(index)
                    href = anchor.get_attribute("href")
                    if not href:
                        continue
                    if href.startswith("/"):
                        href = f"https://job-boards.greenhouse.io{href}"
                    if href in seen_urls:
                        continue

                    text = " ".join(anchor.inner_text().split())
                    if not text:
                        continue

                    parts = [part.strip() for part in re.split(r"\s{2,}|\n", anchor.inner_text()) if part.strip()]
                    title = parts[0] if parts else text
                    location = parts[1] if len(parts) > 1 else board.get("default_location", "")

                    discovered.append(
                        {
                            "title": title,
                            "location": location,
                            "absolute_url": href,
                            "content": "",
                            "metadata": [],
                        }
                    )
                    seen_urls.add(href)
                except Exception:
                    continue

            browser.close()

        return discovered

    def scrape_jobs(self, processed_fingerprints: set[str]) -> List[dict]:
        boards = self._load_config()
        if not boards:
            print("   [!] No company boards configured.")
            return []

        discovered_by_url: Dict[str, dict] = {}
        inspected_boards = 0

        for board in boards:
            company = board.get("company", "Unknown Company")
            ats = (board.get("ats") or "").strip().lower()
            print(f"Scanning company board: {company} ({ats})")
            try:
                if ats == "lever":
                    jobs = self._scrape_lever_board(board, processed_fingerprints)
                elif ats == "greenhouse":
                    jobs = self._scrape_greenhouse_board(board, processed_fingerprints)
                else:
                    print(f"   [!] Unsupported ATS: {ats}")
                    continue

                inspected_boards += 1
                for job in jobs:
                    discovered_by_url.setdefault(job["url"], job)
                print(f"   -> Kept {len(jobs)} matching jobs from {company}.")
            except Exception as exc:
                print(f"   [!] Failed to scan {company}: {exc}")

        print(
            f"Company boards summary: scanned {inspected_boards} boards, "
            f"kept {len(discovered_by_url)} unique jobs."
        )
        return list(discovered_by_url.values())

    def enrich_jobs(self, jobs: Sequence[dict]) -> List[dict]:
        enriched_jobs = []
        for job in jobs:
            updated_job = dict(job)
            if not updated_job.get("full_description"):
                updated_job["full_description"] = (
                    "Manual review required: Company board description was not available from API."
                )
            enriched_jobs.append(updated_job)
        return enriched_jobs


SOURCE_REGISTRY: Dict[str, JobSource] = {
    CompanyBoardsSource.source_name: CompanyBoardsSource(),
    JobBankSource.source_name: JobBankSource(),
    LinkedInSource.source_name: LinkedInSource(),
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
