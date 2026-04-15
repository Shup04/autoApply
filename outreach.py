import argparse
import json
import os
import re
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from utils import (
    APPLICATION_STATUS_FILE,
    BASE_DIR,
    build_job_artifact_label,
    find_record_by_job_id,
    load_application_statuses,
    save_application_statuses,
    utc_now_iso,
)

OUTREACH_DIR = os.path.join(BASE_DIR, "outreach")
JOBS_WITH_DESCRIPTIONS_FILE = os.path.join(BASE_DIR, "jobs_with_descriptions.json")

os.makedirs(OUTREACH_DIR, exist_ok=True)
load_dotenv(override=True)
client = OpenAI()


def load_jobs_with_descriptions():
    if not os.path.exists(JOBS_WITH_DESCRIPTIONS_FILE):
        return []
    with open(JOBS_WITH_DESCRIPTIONS_FILE, "r") as file_handle:
        try:
            data = json.load(file_handle)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []


def find_job_details(record):
    jobs = load_jobs_with_descriptions()
    fingerprint = record.get("fingerprint")
    url = record.get("url")
    for job in jobs:
        if fingerprint and job.get("fingerprint") == fingerprint:
            return job
    for job in jobs:
        if url and job.get("url") == url:
            return job
    return {
        "title": record.get("title", ""),
        "company": record.get("company", ""),
        "location": record.get("location", ""),
        "url": record.get("url", ""),
        "full_description": "",
    }


def compact_company_name(company):
    base = re.split(r"\(|-", company)[0].strip()
    return base or company


def default_contact_role_for_job(title):
    normalized = " ".join((title or "").lower().split())
    if "intern" in normalized or "co-op" in normalized or "coop" in normalized:
        return "Engineering Manager or Technical Recruiter"
    return "Hiring Manager"


def build_contact_block(contact_name=None, contact_role=None, contact_email=None):
    role = contact_role or "Unknown role"
    name = contact_name or "Unknown contact"
    email = contact_email or "unknown@company.com"
    return {
        "name": name,
        "role": role,
        "email": email,
        "complete": bool(contact_name and contact_role and contact_email),
    }


def get_outreach_content(record, job, contact):
    with open(os.path.join(BASE_DIR, "persona.txt"), "r") as file_handle:
        voice_reference = file_handle.read()

    prompt = f"""
You are drafting a short, credible post-application outreach email for Bradley Schmidt.

JOB:
- title: {job.get("title", record.get("title", ""))}
- company: {job.get("company", record.get("company", ""))}
- location: {job.get("location", record.get("location", ""))}
- url: {job.get("url", record.get("url", ""))}
- current status: {record.get("status", "")}

TARGET CONTACT:
- name: {contact["name"]}
- role: {contact["role"]}
- email: {contact["email"]}

JOB DESCRIPTION:
{job.get("full_description", "")}

VOICE REFERENCE:
{voice_reference}

GOAL:
- Bradley has already applied or is about to apply.
- Write a short proactive email that sounds sharp, respectful, and technically credible.
- Do not sound needy, spammy, or manipulative.
- The email should make it easy for the recipient to ignore without being annoyed.

RULES:
- Keep the body between 90 and 170 words.
- First person is allowed.
- Mention 1-2 concrete reasons Bradley fits the role.
- Mention one concrete project or experience item from Bradley's background only if relevant.
- Ask for nothing larger than a brief conversation or for the email to be passed along if appropriate.
- No exaggerated flattery.
- No fake familiarity.
- If the contact is incomplete or placeholder-only, write the email so it still works after the placeholders are replaced.

OUTPUT:
Return raw JSON with exactly these keys:
- subject
- email_body
- why_this_contact
- cautions
"""

    response = client.responses.create(
        model="gpt-5.4-mini",
        input=prompt,
        reasoning={"effort": "low"},
    )
    raw_output = response.output_text.strip()
    match = re.search(r"\{.*\}", raw_output, re.DOTALL)
    if match:
        raw_output = match.group(0)
    return json.loads(raw_output)


def save_outreach_markdown(record, contact, draft):
    label = build_job_artifact_label(record.get("company", ""), record.get("title", ""))
    path = os.path.join(OUTREACH_DIR, f"Outreach_{label}.md")
    with open(path, "w") as file_handle:
        file_handle.write(
            "\n".join(
                [
                    f"# Outreach Draft for Job [{record.get('job_id', '?')}]",
                    "",
                    f"Company: {record.get('company', '')}",
                    f"Title: {record.get('title', '')}",
                    f"Location: {record.get('location', '')}",
                    f"Status: {record.get('status', '')}",
                    f"URL: {record.get('url', '')}",
                    "",
                    "## Contact",
                    f"Name: {contact['name']}",
                    f"Role: {contact['role']}",
                    f"Email: {contact['email']}",
                    "",
                    "## Suggested Subject",
                    draft.get("subject", ""),
                    "",
                    "## Draft Email",
                    draft.get("email_body", ""),
                    "",
                    "## Why This Contact",
                    draft.get("why_this_contact", ""),
                    "",
                    "## Cautions",
                    draft.get("cautions", ""),
                    "",
                    "## Next Step",
                    "Replace any placeholder contact fields, then copy the subject and body into Gmail.",
                ]
            )
        )
    return path


def update_record_outreach(record, contact, draft_path):
    statuses = load_application_statuses()
    fingerprint = record["fingerprint"]
    current = statuses.get(fingerprint, dict(record))
    current["outreach"] = {
        "contact_name": contact["name"],
        "contact_role": contact["role"],
        "contact_email": contact["email"],
        "draft_path": draft_path,
        "updated_at": utc_now_iso(),
        "contact_complete": contact["complete"],
    }
    statuses[fingerprint] = current
    save_application_statuses(statuses)
    return current


def draft_outreach(job_id, contact_name=None, contact_role=None, contact_email=None):
    _, record = find_record_by_job_id(job_id)
    if not record:
        raise SystemExit(f"No job found for ID {job_id}.")

    job = find_job_details(record)
    contact = build_contact_block(
        contact_name=contact_name,
        contact_role=contact_role or default_contact_role_for_job(record.get("title", "")),
        contact_email=contact_email,
    )
    draft = get_outreach_content(record, job, contact)
    draft_path = save_outreach_markdown(record, contact, draft)
    update_record_outreach(record, contact, draft_path)
    print(f"Saved outreach draft to {draft_path}")
    print(f"Subject: {draft.get('subject', '')}")
    print()
    print(draft.get("email_body", ""))


def parse_args():
    parser = argparse.ArgumentParser(description="Generate outreach email drafts for tracked jobs.")
    parser.add_argument("job_id", type=int, help="Tracked job ID.")
    parser.add_argument("--contact-name", help="Contact name if you already know it.")
    parser.add_argument("--contact-role", help="Contact role/title if you already know it.")
    parser.add_argument("--contact-email", help="Contact email if you already know it.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    draft_outreach(
        args.job_id,
        contact_name=args.contact_name,
        contact_role=args.contact_role,
        contact_email=args.contact_email,
    )
