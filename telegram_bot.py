import argparse
import json
import os
import re
import time

from notifier import CHAT_ID, delete_telegram_messages, fetch_updates, send_text_message, set_bot_commands
from utils import (
    BASE_DIR,
    backfill_application_job_ids,
    load_application_statuses,
    save_application_statuses,
    utc_now_iso,
)

STATE_FILE = os.path.join(BASE_DIR, "telegram_bot_state.json")

STATUS_ALIASES = {
    "all": "all",
    "bc": "bc",
    "canada": "canada",
    "us": "us",
    "prepared": "prepared",
    "waiting": "prepared",
    "waitingtoapply": "prepared",
    "applied": "applied",
    "interview": "interview",
    "rejected": "rejected",
    "offer": "offer",
    "archived": "archived",
    "hidden": "archived",
    "unhide": "prepared",
}

STATUS_COMMANDS = {"prepared", "applied", "interview", "rejected", "offer", "hide", "archived", "unhide"}
BOT_COMMANDS = [
    {"command": "list", "description": "List jobs by status or region, e.g. /list prepared bc"},
    {"command": "summary", "description": "Show a compact status summary"},
    {"command": "list_bc", "description": "List active tracked jobs in BC"},
    {"command": "list_us", "description": "List tracked jobs whose location looks US-based"},
    {"command": "hide_us", "description": "Archive all tracked jobs whose location looks US-based"},
    {"command": "show", "description": "Show job details by ID, e.g. /show 6"},
    {"command": "note", "description": "Add or clear a note, e.g. /note 6 OA completed"},
    {"command": "applied", "description": "Mark a job applied by ID or search"},
    {"command": "interview", "description": "Mark a job interview by ID or search"},
    {"command": "rejected", "description": "Mark a job rejected by ID or search"},
    {"command": "offer", "description": "Mark a job offer by ID or search"},
    {"command": "prepared", "description": "Mark a job prepared by ID or search"},
    {"command": "hide", "description": "Archive a job and delete its Telegram messages"},
    {"command": "unhide", "description": "Move a hidden job back to prepared"},
    {"command": "help", "description": "Show bot help"},
]


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"last_update_id": None, "pending_actions": {}}
    with open(STATE_FILE, "r") as file_handle:
        try:
            data = json.load(file_handle)
            if isinstance(data, dict):
                data.setdefault("pending_actions", {})
                return data
        except (json.JSONDecodeError, TypeError):
            pass
    return {"last_update_id": None, "pending_actions": {}}


def save_state(state):
    with open(STATE_FILE, "w") as file_handle:
        json.dump(state, file_handle, indent=4, sort_keys=True)


def normalize_status(value):
    key = "".join(value.lower().split())
    return STATUS_ALIASES.get(key)


def load_records():
    statuses = load_application_statuses()
    records = list(statuses.values())
    records.sort(key=lambda record: record.get("updated_at", ""), reverse=True)
    return records


def record_label(record):
    return f"[{record.get('job_id', '?')}] {record.get('company', 'Unknown')} | {record.get('title', 'Unknown')}"


def format_record_line(record):
    return f"[{record.get('job_id', '?')}] {record.get('status', 'unknown')} | {record.get('company', 'Unknown')} | {record.get('title', 'Unknown')}"


def short_company_name(company):
    base = company.split(" - ")[0].strip()
    base = base.split("(")[0].strip()
    return base or company


def compact_title(title, max_length=52):
    clean = " ".join(title.split())
    if len(clean) <= max_length:
        return clean
    return clean[: max_length - 1].rstrip() + "…"


def compact_location(location, max_length=32):
    clean = " ".join((location or "").split())
    if not clean:
        return ""
    if len(clean) <= max_length:
        return clean
    return clean[: max_length - 1].rstrip() + "…"


def status_heading(status):
    labels = {
        "prepared": "Prepared Jobs",
        "applied": "Applied Jobs",
        "interview": "Interview Jobs",
        "rejected": "Rejected Jobs",
        "offer": "Offer Jobs",
        "archived": "Hidden Jobs",
    }
    return labels.get(status, f"{status.title()} Jobs")


def clean_url(url, max_length=90):
    if not url:
        return ""
    if len(url) <= max_length:
        return url
    return url[: max_length - 1] + "…"


def compact_note(note, max_length=100):
    clean = " ".join((note or "").split())
    if not clean:
        return ""
    if len(clean) <= max_length:
        return clean
    return clean[: max_length - 1].rstrip() + "…"


def is_us_location(location):
    normalized = " ".join((location or "").lower().split())
    if not normalized:
        return False
    us_markers = [
        "united states",
        " usa",
        "u.s.",
        "washington, united states",
        "california",
        "massachusetts",
        "north carolina",
        "texas",
        "new york",
        "illinois",
    ]
    has_named_marker = any(marker in normalized for marker in us_markers)
    has_state_abbrev = bool(re.search(r",\s*(wa|ca|ma|nc|tx|ny|il)\b", normalized))
    return has_named_marker or has_state_abbrev


def is_bc_location(location):
    normalized = " ".join((location or "").lower().split())
    if not normalized:
        return False
    bc_markers = [
        "british columbia",
        "vancouver",
        "burnaby",
        "victoria",
        "kelowna",
        "kamloops",
        "surrey",
        "richmond",
        ", bc",
    ]
    return any(marker in normalized for marker in bc_markers)


def is_canada_location(location):
    normalized = " ".join((location or "").lower().split())
    if not normalized:
        return False
    if "canada" in normalized:
        return True
    province_markers = [
        "british columbia",
        "alberta",
        "ontario",
        "manitoba",
        "saskatchewan",
        "nova scotia",
        "new brunswick",
        "newfoundland",
        "prince edward island",
        "quebec",
    ]
    if any(marker in normalized for marker in province_markers):
        return True
    return bool(re.search(r",\s*(bc|ab|on|mb|sk|ns|nb|nl|pe|qc)\b", normalized))


def active_records():
    return [record for record in load_records() if record.get("status") != "archived"]


def records_for_status(status):
    if status == "all":
        return load_records()
    return [record for record in load_records() if record.get("status") == status]


def records_for_region(records, region):
    if region == "us":
        return [record for record in records if is_us_location(record.get("location", ""))]
    if region == "bc":
        return [record for record in records if is_bc_location(record.get("location", ""))]
    if region == "canada":
        return [record for record in records if is_canada_location(record.get("location", ""))]
    return records


def list_us_jobs():
    records = [record for record in active_records() if is_us_location(record.get("location", ""))]
    if not records:
        return "No active US-based jobs."
    lines = [f"US Jobs ({len(records)})"]
    for record in records[:40]:
        lines.append(
            f"[{record.get('job_id', '?')}] "
            f"{short_company_name(record.get('company', 'Unknown'))} | "
            f"{compact_title(record.get('title', 'Unknown'))} "
            f"[{compact_location(record.get('location', ''))}]"
        )
    if len(records) > 40:
        lines.append(f"...and {len(records) - 40} more")
    return "\n".join(lines)


def list_bc_jobs():
    records = [record for record in active_records() if is_bc_location(record.get("location", ""))]
    if not records:
        return "No active BC-based jobs."
    grouped = {}
    for record in records:
        grouped.setdefault(short_company_name(record.get("company", "Unknown")), []).append(record)
    lines = [f"BC Jobs ({len(records)})"]
    shown = 0
    for company in sorted(grouped):
        company_records = sorted(grouped[company], key=lambda record: record.get("job_id", 0))
        lines.append(f"\n{company}")
        for record in company_records:
            if shown >= 40:
                break
            location = compact_location(record.get("location", ""))
            suffix = f" [{location}]" if location else ""
            lines.append(f"[{record.get('job_id', '?')}] {compact_title(record.get('title', 'Unknown'))}{suffix}")
            shown += 1
        if shown >= 40:
            break
    if len(records) > shown:
        lines.append(f"\n...and {len(records) - shown} more")
    return "\n".join(lines)


def list_region_for_status(status, region):
    records = records_for_region(records_for_status(status), region)
    if status != "all":
        records = [record for record in records if record.get("status") != "archived"]
    if not records:
        return f"No jobs matched status `{status}` in region `{region}`."

    heading_bits = []
    if status == "all":
        heading_bits.append("All")
    else:
        heading_bits.append(status_heading(status).replace(" Jobs", ""))
    heading_bits.append(region.upper())
    lines = [f"{' '.join(heading_bits)} Jobs ({len(records)})"]

    grouped = {}
    for record in records:
        grouped.setdefault(short_company_name(record.get("company", "Unknown")), []).append(record)

    shown = 0
    for company in sorted(grouped):
        company_records = sorted(grouped[company], key=lambda record: record.get("job_id", 0))
        lines.append(f"\n{company}")
        for record in company_records:
            if shown >= 40:
                break
            location = compact_location(record.get("location", ""))
            suffix = f" [{location}]" if location else ""
            status_prefix = f"{record.get('status', 'unknown')} | " if status == "all" else ""
            lines.append(f"[{record.get('job_id', '?')}] {status_prefix}{compact_title(record.get('title', 'Unknown'))}{suffix}")
            shown += 1
        if shown >= 40:
            break
    if len(records) > shown:
        lines.append(f"\n...and {len(records) - shown} more")
    return "\n".join(lines)


def hide_us_jobs():
    records = [record for record in active_records() if is_us_location(record.get("location", ""))]
    if not records:
        return "No active US-based jobs to hide."
    deleted_messages = 0
    for record in records:
        _, deleted = hide_record(record)
        deleted_messages += deleted
    return (
        f"Hidden {len(records)} US-based jobs.\n"
        f"Deleted Telegram messages: {deleted_messages}"
    )


def find_record_by_id(job_id):
    for record in load_records():
        if record.get("job_id") == job_id:
            return record
    return None


def search_records(query):
    normalized = query.lower().strip()
    matches = []
    for record in load_records():
        haystack = " ".join(
            str(record.get(field, "")).lower()
            for field in ("company", "title", "artifact_label", "fingerprint")
        )
        if normalized in haystack:
            matches.append(record)
    return matches


def update_record(record, status, notes=None):
    statuses = load_application_statuses()
    fingerprint = record["fingerprint"]
    current = statuses.get(fingerprint, dict(record))
    current["status"] = status
    current["updated_at"] = utc_now_iso()
    if status == "applied" and not current.get("applied_at"):
        current["applied_at"] = current["updated_at"]
    if notes:
        current["notes"] = notes
    statuses[fingerprint] = current
    save_application_statuses(statuses)
    return current


def set_record_note(record, note_text):
    statuses = load_application_statuses()
    fingerprint = record["fingerprint"]
    current = statuses.get(fingerprint, dict(record))
    if note_text:
        current["notes"] = note_text
    else:
        current.pop("notes", None)
    current["updated_at"] = utc_now_iso()
    statuses[fingerprint] = current
    save_application_statuses(statuses)
    return current


def hide_record(record):
    updated = update_record(record, "archived")
    deleted = delete_telegram_messages(updated.get("telegram_message_ids", []))
    return updated, deleted


def list_status(status):
    if status == "all":
        records = load_records()
        if not records:
            return "No tracked jobs yet."
        counts = {}
        for record in records:
            counts[record.get("status", "unknown")] = counts.get(record.get("status", "unknown"), 0) + 1
        lines = [f"All Jobs ({len(records)})"]
        for key in ["prepared", "applied", "interview", "offer", "rejected", "archived"]:
            if counts.get(key):
                lines.append(f"{key}: {counts[key]}")
        lines.append("")
        lines.append("Recent jobs:")
        for record in records[:20]:
            location = compact_location(record.get("location", ""))
            suffix = f" [{location}]" if location else ""
            lines.append(
                f"[{record.get('job_id', '?')}] "
                f"{record.get('status', 'unknown')} | "
                f"{short_company_name(record.get('company', 'Unknown'))} | "
                f"{compact_title(record.get('title', 'Unknown'))}{suffix}"
            )
        if len(records) > 20:
            lines.append(f"...and {len(records) - 20} more")
        return "\n".join(lines)

    records = [record for record in load_records() if record.get("status") == status]
    if not records:
        return f"No jobs with status `{status}`."
    grouped = {}
    for record in records:
        grouped.setdefault(short_company_name(record.get("company", "Unknown")), []).append(record)

    lines = [f"{status_heading(status)} ({len(records)})"]
    shown = 0
    for company in sorted(grouped):
        company_records = sorted(grouped[company], key=lambda record: record.get("job_id", 0))
        lines.append(f"\n{company}")
        for record in company_records:
            if shown >= 40:
                break
            location = compact_location(record.get("location", ""))
            suffix = f" [{location}]" if location else ""
            lines.append(f"[{record.get('job_id', '?')}] {compact_title(record.get('title', 'Unknown'))}{suffix}")
            shown += 1
        if shown >= 40:
            break
    if len(records) > shown:
        lines.append(f"\n...and {len(records) - shown} more")
    return "\n".join(lines)


def summary_text():
    records = load_records()
    if not records:
        return "No tracked jobs yet."

    counts = {}
    for record in records:
        counts[record.get("status", "unknown")] = counts.get(record.get("status", "unknown"), 0) + 1

    active = [record for record in records if record.get("status") != "archived"]
    bc_count = sum(1 for record in active if is_bc_location(record.get("location", "")))
    canada_count = sum(1 for record in active if is_canada_location(record.get("location", "")))
    us_count = sum(1 for record in active if is_us_location(record.get("location", "")))

    lines = [f"Status Summary ({len(records)} total)"]
    for key in ["prepared", "applied", "interview", "offer", "rejected", "archived"]:
        if counts.get(key):
            lines.append(f"{key}: {counts[key]}")

    lines.extend(
        [
            "",
            f"active: {len(active)}",
            f"bc: {bc_count}",
            f"canada: {canada_count}",
            f"us: {us_count}",
            "",
            "Recent updates:",
        ]
    )

    for record in records[:8]:
        location = compact_location(record.get("location", ""))
        suffix = f" [{location}]" if location else ""
        lines.append(
            f"[{record.get('job_id', '?')}] "
            f"{record.get('status', 'unknown')} | "
            f"{short_company_name(record.get('company', 'Unknown'))} | "
            f"{compact_title(record.get('title', 'Unknown'))}{suffix}"
        )

    return "\n".join(lines)


def recent_records_text(status=None, limit=8):
    records = load_records()
    if status is not None:
        records = [record for record in records if record.get("status") == status]
    records = records[:limit]
    if not records:
        return "No matching jobs."
    lines = []
    for record in records:
        location = compact_location(record.get("location", ""))
        suffix = f" [{location}]" if location else ""
        lines.append(f"{record_label(record)}{suffix}")
    return "\n".join(lines)


def parse_list_like_argument(argument):
    args = argument.split()
    if not args or len(args) > 2:
        return None
    if len(args) == 1:
        token = normalize_status(args[0])
        if not token:
            return None
        if token in {"us", "bc", "canada"}:
            return ("region", "all", token)
        return ("status", token, None)
    status = normalize_status(args[0])
    region = normalize_status(args[1])
    if not status or region not in {"us", "bc", "canada"}:
        return None
    return ("status_region", status, region)


def send_list_like_response(argument, reply_to_message_id):
    parsed = parse_list_like_argument(argument)
    if not parsed:
        send_text_message(
            "\n".join(
                [
                    "Usage: /list <status>",
                    "Usage: /list <region>",
                    "Usage: /list <status> <region>",
                    "Examples:",
                    "/list prepared",
                    "/list prepared bc",
                    "/list us",
                ]
            ),
            reply_to_message_id=reply_to_message_id,
        )
        return

    mode, status, region = parsed
    if mode == "region":
        if region == "us":
            send_text_message(list_us_jobs(), reply_to_message_id=reply_to_message_id)
            return
        if region == "bc":
            send_text_message(list_bc_jobs(), reply_to_message_id=reply_to_message_id)
            return
        send_text_message(list_region_for_status("all", "canada"), reply_to_message_id=reply_to_message_id)
        return
    if mode == "status":
        send_text_message(list_status(status), reply_to_message_id=reply_to_message_id)
        return
    send_text_message(list_region_for_status(status, region), reply_to_message_id=reply_to_message_id)


def show_record(record):
    resume_name = os.path.basename(record.get("resume_path", "")) or "missing"
    cover_name = os.path.basename(record.get("cover_letter_path", "")) or "missing"
    note_line = f"Note: {record.get('notes', '').strip()}" if record.get("notes") else "Note: None"
    return "\n".join(
        [
            f"Job [{record.get('job_id', '?')}]",
            f"{record.get('company', 'Unknown')}",
            compact_title(record.get('title', 'Unknown'), max_length=80),
            "",
            f"Status: {record.get('status', 'unknown')}",
            f"Location: {record.get('location', 'Unknown') or 'Unknown'}",
            note_line,
            f"Resume: {resume_name}",
            f"Cover Letter: {cover_name}",
            f"URL: {clean_url(record.get('url', ''))}",
        ]
    )


def parse_note_argument(argument):
    parts = argument.split(maxsplit=1)
    if not parts or not parts[0].isdigit():
        return None, None
    job_id = int(parts[0])
    note_text = parts[1].strip() if len(parts) > 1 else ""
    return job_id, note_text


def handle_mark_like(command, query, chat_key, reply_to_message_id, state):
    target_status = "archived" if command == "hide" else normalize_status(command)
    if not target_status:
        send_text_message("Unknown status command.", reply_to_message_id=reply_to_message_id)
        return

    if query.isdigit():
        record = find_record_by_id(int(query))
        if not record:
            send_text_message(f"No job found for ID `{query}`.", reply_to_message_id=reply_to_message_id)
            return
        if command == "hide":
            updated, deleted = hide_record(record)
            send_text_message(
                "\n".join(
                    [
                        f"Hidden Job [{updated.get('job_id', '?')}]",
                        f"{short_company_name(updated.get('company', 'Unknown'))}",
                        compact_title(updated.get('title', 'Unknown')),
                        f"Deleted Telegram messages: {deleted}",
                    ]
                ),
                reply_to_message_id=reply_to_message_id,
            )
        else:
            updated = update_record(record, target_status)
            send_text_message(
                "\n".join(
                    [
                        f"Updated Job [{updated.get('job_id', '?')}]",
                        f"{short_company_name(updated.get('company', 'Unknown'))}",
                        compact_title(updated.get('title', 'Unknown')),
                        f"New status: {updated['status']}",
                    ]
                ),
                reply_to_message_id=reply_to_message_id,
            )
        state["pending_actions"].pop(chat_key, None)
        return

    matches = search_records(query)
    if not matches:
        send_text_message(f"No jobs matched `{query}`.", reply_to_message_id=reply_to_message_id)
        return
    if len(matches) == 1:
        only = matches[0]
        if command == "hide":
            updated, deleted = hide_record(only)
            send_text_message(
                "\n".join(
                    [
                        f"Hidden Job [{updated.get('job_id', '?')}]",
                        f"{short_company_name(updated.get('company', 'Unknown'))}",
                        compact_title(updated.get('title', 'Unknown')),
                        f"Deleted Telegram messages: {deleted}",
                    ]
                ),
                reply_to_message_id=reply_to_message_id,
            )
        else:
            updated = update_record(only, target_status)
            send_text_message(
                "\n".join(
                    [
                        f"Updated Job [{updated.get('job_id', '?')}]",
                        f"{short_company_name(updated.get('company', 'Unknown'))}",
                        compact_title(updated.get('title', 'Unknown')),
                        f"New status: {updated['status']}",
                    ]
                ),
                reply_to_message_id=reply_to_message_id,
            )
        state["pending_actions"].pop(chat_key, None)
        return

    candidate_ids = [record["job_id"] for record in matches[:10]]
    state["pending_actions"][chat_key] = {"command": command, "candidate_ids": candidate_ids}
    lines = [f"Multiple matches for `{query}`", "", f"Reply with one ID to mark `{target_status}`:"]
    for record in matches[:10]:
        lines.append(f"[{record.get('job_id', '?')}] {short_company_name(record.get('company', 'Unknown'))} | {compact_title(record.get('title', 'Unknown'))}")
    send_text_message("\n".join(lines), reply_to_message_id=reply_to_message_id)


def handle_pending_id(text, chat_key, reply_to_message_id, state):
    pending = state["pending_actions"].get(chat_key)
    if not pending or not text.isdigit():
        return False
    job_id = int(text)
    if job_id not in pending.get("candidate_ids", []):
        send_text_message(
            f"ID `{job_id}` is not one of the pending choices. Send `cancel` to clear.",
            reply_to_message_id=reply_to_message_id,
        )
        return True
    handle_mark_like(pending["command"], text, chat_key, reply_to_message_id, state)
    return True


def handle_text(text, chat_id, message_id, state):
    if str(chat_id) != str(CHAT_ID):
        return

    chat_key = str(chat_id)
    normalized = text.strip()
    lowered = normalized.lower()

    if handle_pending_id(normalized, chat_key, message_id, state):
        return

    if lowered == "help":
        send_text_message(
            "\n".join(
                [
                    "Commands:",
                    "/summary",
                    "/list <status>",
                    "/show <id>",
                    "/note <id> <text>",
                    "/applied <id or search>",
                    "/interview <id or search>",
                    "/rejected <id or search>",
                    "/offer <id or search>",
                    "/prepared <id or search>",
                    "/hide <id or search>",
                    "cancel",
                ]
            ),
            reply_to_message_id=message_id,
        )
        return

    if lowered == "cancel":
        state["pending_actions"].pop(chat_key, None)
        send_text_message("Cleared pending selection.", reply_to_message_id=message_id)
        return

    parts = normalized.split(maxsplit=1)
    command = parts[0].lower()
    if command.startswith("/"):
        command = command[1:]
        if "@" in command:
            command = command.split("@", 1)[0]
    argument = parts[1].strip() if len(parts) > 1 else ""

    if command == "list":
        if not argument:
            send_text_message(
                "\n".join(
                    [
                        "Usage: /list <status>",
                        "Usage: /list <region>",
                        "Usage: /list <status> <region>",
                        "Regions: bc, canada, us",
                        "Statuses: prepared, applied, interview, rejected, offer, hidden, all",
                        "",
                        "Example:",
                        "/list prepared",
                        "/list prepared bc",
                        "/list us",
                    ]
                ),
                reply_to_message_id=message_id,
            )
            return
        send_list_like_response(argument, reply_to_message_id=message_id)
        return

    if command == "summary":
        send_text_message(summary_text(), reply_to_message_id=message_id)
        return

    if command == "list_us":
        send_text_message(list_us_jobs(), reply_to_message_id=message_id)
        return

    if command == "list_bc":
        send_text_message(list_bc_jobs(), reply_to_message_id=message_id)
        return

    if command == "hide_us":
        send_text_message(hide_us_jobs(), reply_to_message_id=message_id)
        return

    if command == "show":
        if not argument:
            send_text_message(
                "\n".join(
                    [
                        "Usage: /show <id>",
                        "Alias: /show <status> <region>",
                        "",
                        "Recent jobs:",
                        recent_records_text(limit=8),
                    ]
                ),
                reply_to_message_id=message_id,
            )
            return
        if not argument.isdigit():
            parsed = parse_list_like_argument(argument)
            if parsed:
                send_list_like_response(argument, reply_to_message_id=message_id)
                return
            send_text_message("Usage: /show <id> or /show prepared bc", reply_to_message_id=message_id)
            return
        record = find_record_by_id(int(argument))
        if not record:
            send_text_message(f"No job found for ID `{argument}`.", reply_to_message_id=message_id)
            return
        send_text_message(show_record(record), reply_to_message_id=message_id)
        return

    if command == "note":
        if not argument:
            send_text_message(
                "\n".join(
                    [
                        "Usage: /note <id> <text>",
                        "Clear: /note <id> clear",
                        "",
                        "Examples:",
                        "/note 6 OA completed",
                        "/note 6 waiting on referral",
                    ]
                ),
                reply_to_message_id=message_id,
            )
            return
        job_id, note_text = parse_note_argument(argument)
        if not job_id:
            send_text_message("Usage: /note <id> <text>", reply_to_message_id=message_id)
            return
        record = find_record_by_id(job_id)
        if not record:
            send_text_message(f"No job found for ID `{job_id}`.", reply_to_message_id=message_id)
            return
        normalized_note = note_text.strip()
        clear_note = normalized_note.lower() in {"clear", "delete", "remove", "-", "none"}
        updated = set_record_note(record, "" if clear_note else normalized_note)
        lines = [
            f"Updated Note for Job [{updated.get('job_id', '?')}]",
            f"{short_company_name(updated.get('company', 'Unknown'))}",
            compact_title(updated.get('title', 'Unknown')),
        ]
        if clear_note:
            lines.append("Note cleared.")
        else:
            lines.append(f"Note: {compact_note(updated.get('notes', ''))}")
        send_text_message("\n".join(lines), reply_to_message_id=message_id)
        return

    if command in STATUS_COMMANDS:
        if not argument:
            suggested_status = "archived" if command == "unhide" else ("prepared" if command in {"applied", "interview", "rejected", "offer", "hide"} else None)
            send_text_message(
                "\n".join(
                    [
                        f"Usage: /{command} <id or search text>",
                        "",
                        "Examples:",
                        f"/{command} 6",
                        f"/{command} hootsuite",
                        "",
                        "Recent matching jobs:",
                        recent_records_text(status=suggested_status, limit=8),
                    ]
                ),
                reply_to_message_id=message_id,
            )
            return
        handle_mark_like(command, argument, chat_key, message_id, state)
        return

    send_text_message("Unknown command. Send `help`.", reply_to_message_id=message_id)


def process_updates(updates, state):
    for update in updates:
        state["last_update_id"] = update["update_id"] + 1
        message = update.get("message") or {}
        text = message.get("text")
        if not text:
            continue
        chat = message.get("chat") or {}
        handle_text(text, chat.get("id"), message.get("message_id"), state)


def run_bot(run_once=False):
    backfill_application_job_ids()
    state = load_state()
    while True:
        updates = fetch_updates(offset=state.get("last_update_id"), timeout=30)
        process_updates(updates, state)
        save_state(state)
        if run_once:
            break
        if not updates:
            time.sleep(1)


def register_commands():
    set_bot_commands(BOT_COMMANDS)
    print("Registered Telegram slash commands.")


def parse_args():
    parser = argparse.ArgumentParser(description="Telegram job status bot.")
    parser.add_argument("--once", action="store_true", help="Process a single getUpdates cycle and exit.")
    parser.add_argument("--register-commands", action="store_true", help="Register slash commands with Telegram and exit.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.register_commands:
        register_commands()
        raise SystemExit(0)
    run_bot(run_once=args.once)
