import argparse
import json
import os
import shutil
import re
from collections import Counter
from datetime import datetime

from utils import (
    APPLICATION_STATUS_FILE,
    BASE_DIR,
    find_record_by_job_id,
    build_job_artifact_label,
    generate_fingerprint,
    is_software_coop_role,
    load_application_statuses,
    save_application_statuses,
    upsert_application_record,
)

SCRAPED_JOBS_FILE = os.path.join(BASE_DIR, "scraped_jobs.json")
DESCRIBED_JOBS_FILE = os.path.join(BASE_DIR, "jobs_with_descriptions.json")
PROCESSED_FILE = os.path.join(BASE_DIR, "processed_jobs.json")
RESUME_DIR = os.path.join(BASE_DIR, "resumes")
COVER_LETTER_DIR = os.path.join(BASE_DIR, "cover_letters")
BUILD_DIR = os.path.join(BASE_DIR, "build")
ARCHIVE_ROOT = os.path.join(BASE_DIR, "archive")


def load_jobs(path):
    if not os.path.exists(path):
        return []
    with open(path, "r") as file_handle:
        try:
            data = json.load(file_handle)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []


def find_job(identifier):
    if identifier.isdigit():
        _, record = find_record_by_job_id(int(identifier))
        if record:
            return {
                "fingerprint": record.get("fingerprint"),
                "title": record.get("title", ""),
                "company": record.get("company", ""),
                "url": record.get("url", ""),
                "source": record.get("source", ""),
            }
    jobs = load_jobs(DESCRIBED_JOBS_FILE)
    if not jobs:
        return None

    normalized = identifier.strip().lower()
    for job in jobs:
        fingerprint = job.get("fingerprint") or generate_fingerprint(job["title"], job["company"])
        artifact_label = build_job_artifact_label(job["company"], job["title"])
        if normalized in {
            fingerprint.lower(),
            job.get("url", "").lower(),
            artifact_label.lower(),
        }:
            return job
    return None


def mark_status(identifier, status, notes=None):
    job = find_job(identifier)
    if not job:
        raise SystemExit(f"Job not found for identifier: {identifier}")

    extra = {"notes": notes} if notes else {}
    artifact_label = build_job_artifact_label(job["company"], job["title"])
    extra["artifact_label"] = artifact_label
    extra["resume_path"] = os.path.join(RESUME_DIR, f"Resume_Schmidt_{artifact_label}.pdf")
    extra["cover_letter_path"] = os.path.join(COVER_LETTER_DIR, f"CL_Schmidt_{artifact_label}.pdf")
    record = upsert_application_record(job, status, **extra)
    print(
        f"{record['status']}: {record['company']} | {record['title']} | "
        f"{record['fingerprint']}"
    )


def backfill_prepared():
    jobs = load_jobs(DESCRIBED_JOBS_FILE)
    if not jobs:
        print("No jobs found in jobs_with_descriptions.json.")
        return

    created = 0
    for job in jobs:
        artifact_label = build_job_artifact_label(job["company"], job["title"])
        resume_path = os.path.join(RESUME_DIR, f"Resume_Schmidt_{artifact_label}.pdf")
        cover_pdf_path = os.path.join(COVER_LETTER_DIR, f"CL_Schmidt_{artifact_label}.pdf")
        cover_txt_path = os.path.join(COVER_LETTER_DIR, f"CL_Schmidt_{artifact_label}.txt")

        if not os.path.exists(resume_path):
            continue
        if not os.path.exists(cover_pdf_path) and not os.path.exists(cover_txt_path):
            continue

        statuses = load_application_statuses()
        fingerprint = job.get("fingerprint") or generate_fingerprint(job["title"], job["company"])
        existing = statuses.get(fingerprint, {})
        if existing.get("status"):
            continue

        upsert_application_record(
            job,
            "prepared",
            artifact_label=artifact_label,
            resume_path=resume_path,
            cover_letter_path=cover_pdf_path if os.path.exists(cover_pdf_path) else cover_txt_path,
        )
        created += 1

    print(f"Backfilled {created} prepared application records.")


def backfill_locations():
    jobs = load_jobs(DESCRIBED_JOBS_FILE)
    if not jobs:
        print("No jobs found in jobs_with_descriptions.json.")
        return

    statuses = load_application_statuses()
    jobs_by_fingerprint = {}
    for job in jobs:
        fingerprint = job.get("fingerprint") or generate_fingerprint(job["title"], job["company"])
        jobs_by_fingerprint[fingerprint] = job

    def infer_location(record, job):
        if job and job.get("location"):
            return job["location"]

        company = record.get("company", "")
        if " - " in company:
            tail = company.rsplit(" - ", 1)[1].strip()
            generic = {"multiple locations", "nationwide", "remote", "hybrid"}
            if tail and tail.lower() not in generic:
                return tail

        if "(" in company and ")" in company:
            parts = [part.strip() for part in company.split("(") if ")" in part]
            candidates = [part.split(")", 1)[0].strip() for part in parts]
            for candidate in reversed(candidates):
                lower = candidate.lower()
                if "," in candidate and any(
                    token in lower
                    for token in [
                        "british columbia",
                        "alberta",
                        "ontario",
                        "bc",
                        "ab",
                        "on",
                        "canada",
                    ]
                ):
                    return candidate

        return ""

    updated = 0
    for fingerprint, record in statuses.items():
        if record.get("location"):
            continue
        job = jobs_by_fingerprint.get(fingerprint)
        location = infer_location(record, job)
        if not location:
            continue
        record["location"] = location
        updated += 1

    if updated:
        save_application_statuses(statuses)
    print(f"Backfilled location on {updated} application records.")


def print_summary():
    statuses = load_application_statuses()
    if not statuses:
        print("No application records yet.")
        return

    counts = Counter(record.get("status", "unknown") for record in statuses.values())
    print("Application status summary:")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

    print("\nRecent jobs:")
    recent = sorted(
        statuses.values(),
        key=lambda record: record.get("updated_at", ""),
        reverse=True,
    )[:15]
    for record in recent:
        print(
            f"  {record.get('status', 'unknown'):>10} | "
            f"{record.get('company', 'Unknown')} | {record.get('title', 'Unknown')}"
        )


def audit_collisions():
    jobs = load_jobs(DESCRIBED_JOBS_FILE)
    if not jobs:
        print("No jobs found in jobs_with_descriptions.json.")
        return

    groups = {}
    for job in jobs:
        old_label = job["company"].split()[0].replace(",", "").replace(".", "")
        groups.setdefault(old_label, []).append(job)

    found = 0
    for old_label, grouped_jobs in sorted(groups.items()):
        if len(grouped_jobs) < 2:
            continue
        found += 1
        resume_path = os.path.join(RESUME_DIR, f"Resume_Schmidt_{old_label}.pdf")
        cl_txt_path = os.path.join(COVER_LETTER_DIR, f"CL_Schmidt_{old_label}.txt")
        print(f"[{old_label}] {len(grouped_jobs)} jobs")
        print(f"  old resume: {'yes' if os.path.exists(resume_path) else 'no'} | {resume_path}")
        print(f"  old cover txt: {'yes' if os.path.exists(cl_txt_path) else 'no'} | {cl_txt_path}")
        for job in grouped_jobs:
            artifact_label = build_job_artifact_label(job["company"], job["title"])
            print(
                f"  - {job['title']} @ {job['company']} | "
                f"{job.get('fingerprint') or generate_fingerprint(job['title'], job['company'])}"
            )
            print(f"    new artifact label: {artifact_label}")
        print()

    if found == 0:
        print("No old-label collisions found.")


def read_text_if_exists(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", errors="ignore") as file_handle:
        return file_handle.read()


def tokenize(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def significant_tokens(text):
    stopwords = {
        "the", "and", "for", "with", "this", "that", "from", "into", "your", "our", "role",
        "team", "intern", "student", "coop", "co", "op", "summer", "fall", "month", "months",
        "software", "engineer", "developer", "engineering", "data", "canada", "vancouver",
    }
    return {token for token in tokenize(text) if len(token) >= 3 and token not in stopwords}


def score_job_match(job, artifact_text):
    title = job["title"]
    company = job["company"]
    description = job.get("full_description", "")
    artifact_lower = artifact_text.lower()
    title_lower = title.lower()

    score = 0
    reasons = []

    if title_lower in artifact_lower:
        score += 100
        reasons.append("exact title in artifact")

    title_tokens = significant_tokens(title)
    artifact_tokens = tokenize(artifact_text)
    title_overlap = sorted(title_tokens & artifact_tokens)
    if title_overlap:
        score += len(title_overlap) * 8
        reasons.append(f"title token overlap: {', '.join(title_overlap[:6])}")

    company_tokens = significant_tokens(re.split(r"\(|-", company)[0])
    company_overlap = sorted(company_tokens & artifact_tokens)
    if company_overlap:
        score += len(company_overlap) * 5
        reasons.append(f"company overlap: {', '.join(company_overlap[:4])}")

    desc_tokens = significant_tokens(" ".join(description.split()[:300]))
    desc_overlap = sorted(desc_tokens & artifact_tokens)
    if desc_overlap:
        score += min(len(desc_overlap), 8) * 2
        reasons.append(f"description overlap: {', '.join(desc_overlap[:6])}")

    if is_software_coop_role(title, description):
        score += 5
        reasons.append("software-role bonus")

    return score, reasons


def detect_collision_groups():
    jobs = load_jobs(DESCRIBED_JOBS_FILE)
    groups = {}
    for job in jobs:
        old_label = job["company"].split()[0].replace(",", "").replace(".", "")
        groups.setdefault(old_label, []).append(job)
    return {label: jobs for label, jobs in groups.items() if len(jobs) > 1}


def analyze_collision_group(old_label, grouped_jobs):
    cl_txt_path = os.path.join(COVER_LETTER_DIR, f"CL_Schmidt_{old_label}.txt")
    tex_path = os.path.join(BUILD_DIR, f"Resume_Schmidt_{old_label}.tex")
    artifact_text = "\n".join([read_text_if_exists(cl_txt_path), read_text_if_exists(tex_path)]).strip()
    if not artifact_text:
        return {"status": "missing-artifact", "old_label": old_label, "jobs": grouped_jobs}

    ranked = []
    for job in grouped_jobs:
        score, reasons = score_job_match(job, artifact_text)
        ranked.append({"job": job, "score": score, "reasons": reasons})
    ranked.sort(key=lambda item: item["score"], reverse=True)

    best = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    confident = best["score"] >= 30 and (second is None or best["score"] - second["score"] >= 12)
    return {
        "status": "matched" if confident else "ambiguous",
        "old_label": old_label,
        "artifact_text_present": True,
        "ranked": ranked,
    }


def copy_if_exists(source, destination):
    if os.path.exists(source):
        shutil.copy2(source, destination)
        return True
    return False


def repair_collisions(execute=False, include_non_software=False):
    groups = detect_collision_groups()
    if not groups:
        print("No collisions found.")
        return

    repaired = 0
    ambiguous = 0
    missing = 0

    for old_label, grouped_jobs in sorted(groups.items()):
        result = analyze_collision_group(old_label, grouped_jobs)
        status = result["status"]
        print(f"[{old_label}] {status}")

        if status == "missing-artifact":
            missing += 1
            continue

        best = result["ranked"][0]
        for item in result["ranked"][:3]:
            job = item["job"]
            print(
                f"  {item['score']:>3} | {job['title']} @ {job['company']} | "
                f"{'; '.join(item['reasons'][:3])}"
            )

        if status != "matched":
            ambiguous += 1
            continue

        job = best["job"]
        if not include_non_software and not is_software_coop_role(job["title"], job.get("full_description", "")):
            print("  skipped -> best match is not a software co-op role")
            continue
        new_label = build_job_artifact_label(job["company"], job["title"])
        old_resume_pdf = os.path.join(RESUME_DIR, f"Resume_Schmidt_{old_label}.pdf")
        old_cl_txt = os.path.join(COVER_LETTER_DIR, f"CL_Schmidt_{old_label}.txt")
        old_cl_pdf = os.path.join(COVER_LETTER_DIR, f"CL_Schmidt_{old_label}.pdf")
        old_build_tex = os.path.join(BUILD_DIR, f"Resume_Schmidt_{old_label}.tex")

        print(f"  selected -> {new_label}")
        if execute:
            copy_if_exists(old_resume_pdf, os.path.join(RESUME_DIR, f"Resume_Schmidt_{new_label}.pdf"))
            copy_if_exists(old_cl_txt, os.path.join(COVER_LETTER_DIR, f"CL_Schmidt_{new_label}.txt"))
            copy_if_exists(old_cl_pdf, os.path.join(COVER_LETTER_DIR, f"CL_Schmidt_{new_label}.pdf"))
            copy_if_exists(old_build_tex, os.path.join(BUILD_DIR, f"Resume_Schmidt_{new_label}.tex"))
            upsert_application_record(
                job,
                "prepared",
                artifact_label=new_label,
                resume_path=os.path.join(RESUME_DIR, f"Resume_Schmidt_{new_label}.pdf"),
                cover_letter_path=os.path.join(COVER_LETTER_DIR, f"CL_Schmidt_{new_label}.pdf"),
                repaired_from_old_label=old_label,
            )
            repaired += 1

    print(
        f"\nSummary: repaired={repaired if execute else 0}, "
        f"ambiguous={ambiguous}, missing_artifact={missing}"
    )
    if not execute:
        print("Dry run only. Re-run with --execute to copy confident matches into the new filenames.")


def archive_file(path, destination_dir):
    if not os.path.exists(path):
        return
    shutil.copy2(path, os.path.join(destination_dir, os.path.basename(path)))


def archive_directory_contents(path, destination_dir):
    if not os.path.isdir(path):
        return
    target_dir = os.path.join(destination_dir, os.path.basename(path))
    os.makedirs(target_dir, exist_ok=True)
    for name in os.listdir(path):
        source = os.path.join(path, name)
        destination = os.path.join(target_dir, name)
        if os.path.isfile(source):
            shutil.copy2(source, destination)


def reset_file_to_empty_json(path, empty_value):
    with open(path, "w") as file_handle:
        json.dump(empty_value, file_handle, indent=4)


def clear_generated_directory(path):
    if not os.path.isdir(path):
        return
    for name in os.listdir(path):
        full_path = os.path.join(path, name)
        if os.path.isfile(full_path):
            os.remove(full_path)


def clean_slate():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = os.path.join(ARCHIVE_ROOT, f"clean_slate_{timestamp}")
    os.makedirs(archive_dir, exist_ok=True)

    for path in [SCRAPED_JOBS_FILE, DESCRIBED_JOBS_FILE, PROCESSED_FILE, APPLICATION_STATUS_FILE]:
        archive_file(path, archive_dir)
    for directory in [RESUME_DIR, COVER_LETTER_DIR, BUILD_DIR]:
        archive_directory_contents(directory, archive_dir)

    reset_file_to_empty_json(SCRAPED_JOBS_FILE, [])
    reset_file_to_empty_json(DESCRIBED_JOBS_FILE, [])
    reset_file_to_empty_json(PROCESSED_FILE, [])
    if os.path.exists(APPLICATION_STATUS_FILE):
        save_application_statuses(load_application_statuses())
    clear_generated_directory(RESUME_DIR)
    clear_generated_directory(COVER_LETTER_DIR)
    clear_generated_directory(BUILD_DIR)

    print(f"Archived current state to: {archive_dir}")
    print("Reset scraped/described/processed files and cleared generated artifacts.")


def parse_args():
    parser = argparse.ArgumentParser(description="Manage job application state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("summary", help="Show local application status summary.")
    subparsers.add_parser("backfill-prepared", help="Create prepared records for jobs with existing artifacts.")
    subparsers.add_parser("backfill-locations", help="Fill missing location fields from the job cache.")
    subparsers.add_parser("audit-collisions", help="List jobs that collided under the old filename scheme.")
    subparsers.add_parser("clean-slate", help="Archive current data and reset generated state.")
    repair_parser = subparsers.add_parser(
        "repair-collisions",
        help="Infer and relabel old collided artifacts into the new filename scheme.",
    )
    repair_parser.add_argument("--execute", action="store_true", help="Apply the repair instead of dry-run.")
    repair_parser.add_argument(
        "--include-non-software",
        action="store_true",
        help="Also repair confident non-software matches.",
    )

    mark_parser = subparsers.add_parser("mark", help="Mark a job with a local application status.")
    mark_parser.add_argument("identifier", help="Fingerprint, URL, or artifact label.")
    mark_parser.add_argument(
        "status",
        choices=["prepared", "applied", "interview", "rejected", "offer", "archived"],
    )
    mark_parser.add_argument("--notes", help="Optional notes to store on the job record.")

    return parser.parse_args()


def main():
    args = parse_args()
    if args.command == "summary":
        print_summary()
        return
    if args.command == "backfill-prepared":
        backfill_prepared()
        return
    if args.command == "backfill-locations":
        backfill_locations()
        return
    if args.command == "audit-collisions":
        audit_collisions()
        return
    if args.command == "clean-slate":
        clean_slate()
        return
    if args.command == "repair-collisions":
        repair_collisions(execute=args.execute, include_non_software=args.include_non_software)
        return
    if args.command == "mark":
        mark_status(args.identifier, args.status, notes=args.notes)
        return


if __name__ == "__main__":
    main()
