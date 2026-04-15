import os
import json
import re
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_FILE = os.path.join(BASE_DIR, "processed_jobs.json")
APPLICATION_STATUS_FILE = os.path.join(BASE_DIR, "application_status.json")

ROLE_EXCLUSION_TERMS = (
    "account executive",
    "accountant",
    "accounting",
    "analyst",
    "bookkeeper",
    "business",
    "customer success",
    "designer",
    "director",
    "finance",
    "financial",
    "hr",
    "human resources",
    "manager",
    "marketing",
    "payroll",
    "product manager",
    "project manager",
    "recruiter",
    "sales",
    "security",
    "talent",
)

SOFTWARE_ROLE_PHRASES = (
    "software developer",
    "software engineer",
    "software engineering",
    "application developer",
    "application engineer",
    "web developer",
    "web engineer",
    "frontend developer",
    "frontend engineer",
    "front end developer",
    "front end engineer",
    "backend developer",
    "backend engineer",
    "back end developer",
    "back end engineer",
    "full stack developer",
    "full stack engineer",
    "full-stack developer",
    "full-stack engineer",
    "mobile developer",
    "mobile engineer",
    "ios developer",
    "android developer",
    "firmware developer",
    "firmware engineer",
    "embedded software",
    "embedded developer",
    "embedded engineer",
    "platform engineer",
    "platform developer",
    "systems developer",
    "systems engineer",
    "developer co-op",
    "developer coop",
    "developer intern",
    "engineer co-op",
    "engineer coop",
    "engineer intern",
)

EXPERIENCE_TERMS = ("intern", "internship", "co-op", "coop", "student")

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


def slugify(value):
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "job"


def build_job_artifact_label(company, title, max_length=80):
    company_slug = slugify(re.split(r"\(|-", company)[0].strip())
    title_slug = slugify(title)
    label = f"{company_slug}_{title_slug}".strip("_")
    return label[:max_length].rstrip("_") or company_slug or title_slug or "job"


def is_software_coop_role(title, extra_text=""):
    normalized_title = " ".join(title.lower().split())
    normalized_blob = " ".join(f"{title} {extra_text}".lower().split())

    if any(term in normalized_title for term in ROLE_EXCLUSION_TERMS):
        return False

    if not any(term in normalized_blob for term in EXPERIENCE_TERMS):
        return False

    if any(phrase in normalized_title for phrase in SOFTWARE_ROLE_PHRASES):
        return True

    token_pairs = (
        ("software", "developer"),
        ("software", "engineer"),
        ("firmware", "developer"),
        ("firmware", "engineer"),
        ("frontend", "developer"),
        ("frontend", "engineer"),
        ("backend", "developer"),
        ("backend", "engineer"),
        ("mobile", "developer"),
        ("mobile", "engineer"),
        ("platform", "developer"),
        ("platform", "engineer"),
        ("embedded", "developer"),
        ("embedded", "engineer"),
        ("web", "developer"),
        ("web", "engineer"),
    )
    return any(all(token in normalized_title for token in pair) for pair in token_pairs)

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


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_application_statuses():
    if os.path.exists(APPLICATION_STATUS_FILE):
        with open(APPLICATION_STATUS_FILE, "r") as file_handle:
            try:
                data = json.load(file_handle)
                return data if isinstance(data, dict) else {}
            except (json.JSONDecodeError, TypeError):
                return {}
    return {}


def save_application_statuses(statuses):
    with open(APPLICATION_STATUS_FILE, "w") as file_handle:
        json.dump(statuses, file_handle, indent=4, sort_keys=True)


def next_job_id(statuses):
    existing_ids = [
        record.get("job_id")
        for record in statuses.values()
        if isinstance(record, dict) and isinstance(record.get("job_id"), int)
    ]
    return (max(existing_ids) + 1) if existing_ids else 1


def find_record_by_job_id(job_id):
    statuses = load_application_statuses()
    for fingerprint, record in statuses.items():
        if record.get("job_id") == job_id:
            return fingerprint, record
    return None, None


def backfill_application_job_ids():
    statuses = load_application_statuses()
    updated = 0
    next_id = next_job_id(statuses)
    for record in statuses.values():
        if not isinstance(record.get("job_id"), int):
            record["job_id"] = next_id
            next_id += 1
            updated += 1
    if updated:
        save_application_statuses(statuses)
    return updated


def upsert_application_record(job, status, **extra_fields):
    fingerprint = job.get("fingerprint") or generate_fingerprint(job["title"], job["company"])
    statuses = load_application_statuses()
    existing = statuses.get(fingerprint, {})

    record = {
        "fingerprint": fingerprint,
        "title": job.get("title", existing.get("title", "")),
        "company": job.get("company", existing.get("company", "")),
        "location": job.get("location", existing.get("location", "")),
        "url": job.get("url", existing.get("url", "")),
        "source": job.get("source", existing.get("source", "")),
        "status": status,
        "updated_at": utc_now_iso(),
    }
    if isinstance(existing.get("job_id"), int):
        record["job_id"] = existing["job_id"]
    else:
        record["job_id"] = next_job_id(statuses)
    if "created_at" in existing:
        record["created_at"] = existing["created_at"]
    else:
        record["created_at"] = record["updated_at"]

    if existing.get("applied_at"):
        record["applied_at"] = existing["applied_at"]

    if status == "applied" and not record.get("applied_at"):
        record["applied_at"] = record["updated_at"]

    merged = {**existing, **record, **extra_fields}
    statuses[fingerprint] = merged
    save_application_statuses(statuses)
    return merged
