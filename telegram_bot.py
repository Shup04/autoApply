import argparse
import json
import os
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
    "prepared": "prepared",
    "waiting": "prepared",
    "waitingtoapply": "prepared",
    "applied": "applied",
    "interview": "interview",
    "rejected": "rejected",
    "offer": "offer",
    "archived": "archived",
    "hidden": "archived",
}

STATUS_COMMANDS = {"prepared", "applied", "interview", "rejected", "offer", "hide", "archived"}
BOT_COMMANDS = [
    {"command": "list", "description": "List jobs by status, e.g. /list prepared"},
    {"command": "show", "description": "Show job details by ID, e.g. /show 6"},
    {"command": "applied", "description": "Mark a job applied by ID or search"},
    {"command": "interview", "description": "Mark a job interview by ID or search"},
    {"command": "rejected", "description": "Mark a job rejected by ID or search"},
    {"command": "offer", "description": "Mark a job offer by ID or search"},
    {"command": "prepared", "description": "Mark a job prepared by ID or search"},
    {"command": "hide", "description": "Archive a job and delete its Telegram messages"},
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


def hide_record(record):
    updated = update_record(record, "archived")
    deleted = delete_telegram_messages(updated.get("telegram_message_ids", []))
    return updated, deleted


def list_status(status):
    records = [record for record in load_records() if record.get("status") == status]
    if not records:
        return f"No jobs with status `{status}`."
    lines = [f"Jobs with status `{status}` ({len(records)}):"]
    for record in records[:40]:
        lines.append(format_record_line(record))
    if len(records) > 40:
        lines.append(f"...and {len(records) - 40} more")
    return "\n".join(lines)


def recent_records_text(status=None, limit=8):
    records = load_records()
    if status is not None:
        records = [record for record in records if record.get("status") == status]
    records = records[:limit]
    if not records:
        return "No matching jobs."
    return "\n".join(record_label(record) for record in records)


def show_record(record):
    resume_name = os.path.basename(record.get("resume_path", "")) or "missing"
    cover_name = os.path.basename(record.get("cover_letter_path", "")) or "missing"
    return "\n".join(
        [
            record_label(record),
            f"Status: {record.get('status', 'unknown')}",
            f"Resume: {resume_name}",
            f"Cover Letter: {cover_name}",
            f"URL: {record.get('url', '')}",
        ]
    )


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
                f"Archived {record_label(updated)}. Deleted {deleted} Telegram messages.",
                reply_to_message_id=reply_to_message_id,
            )
        else:
            updated = update_record(record, target_status)
            send_text_message(
                f"Updated {record_label(updated)} -> {updated['status']}",
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
                f"Archived {record_label(updated)}. Deleted {deleted} Telegram messages.",
                reply_to_message_id=reply_to_message_id,
            )
        else:
            updated = update_record(only, target_status)
            send_text_message(
                f"Updated {record_label(updated)} -> {updated['status']}",
                reply_to_message_id=reply_to_message_id,
            )
        state["pending_actions"].pop(chat_key, None)
        return

    candidate_ids = [record["job_id"] for record in matches[:10]]
    state["pending_actions"][chat_key] = {"command": command, "candidate_ids": candidate_ids}
    lines = [f"Multiple matches for `{query}`. Reply with one of these IDs to mark `{target_status}`:"]
    for record in matches[:10]:
        lines.append(record_label(record))
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
                    "list <status>",
                    "show <id>",
                    "applied <id or search>",
                    "interview <id or search>",
                    "rejected <id or search>",
                    "offer <id or search>",
                    "prepared <id or search>",
                    "hide <id or search>",
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
                        "Usage: /list prepared|applied|interview|rejected|offer|hidden",
                        "",
                        "Example:",
                        "/list prepared",
                    ]
                ),
                reply_to_message_id=message_id,
            )
            return
        status = normalize_status(argument)
        if not status:
            send_text_message(
                "Usage: /list prepared|applied|interview|rejected|offer|hidden",
                reply_to_message_id=message_id,
            )
            return
        send_text_message(list_status(status), reply_to_message_id=message_id)
        return

    if command == "show":
        if not argument:
            send_text_message(
                "\n".join(
                    [
                        "Usage: /show <id>",
                        "",
                        "Recent jobs:",
                        recent_records_text(limit=8),
                    ]
                ),
                reply_to_message_id=message_id,
            )
            return
        if not argument.isdigit():
            send_text_message("Usage: /show <id>", reply_to_message_id=message_id)
            return
        record = find_record_by_id(int(argument))
        if not record:
            send_text_message(f"No job found for ID `{argument}`.", reply_to_message_id=message_id)
            return
        send_text_message(show_record(record), reply_to_message_id=message_id)
        return

    if command in STATUS_COMMANDS:
        if not argument:
            suggested_status = "prepared" if command in {"applied", "interview", "rejected", "offer", "hide"} else None
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
