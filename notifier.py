import requests
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

def _post(endpoint, **kwargs):
    response = requests.post(f"{BASE_URL}/{endpoint}", **kwargs)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")
    return payload["result"]


def send_job_alert(job_id, job_title, company, url, pdf_path, cl_path):
    message_ids = []
    resume_name = os.path.basename(pdf_path)
    cover_name = os.path.basename(cl_path)
    message = (
        f"🎯 *New Job Prepared*\n\n"
        f"*ID:* `{job_id}`\n"
        f"*Title:* {job_title}\n"
        f"*Company:* {company}\n"
        f"*Resume:* `{resume_name}`\n"
        f"*Cover Letter:* `{cover_name}`\n\n"
        f"[View Posting]({url})"
    )
    result = _post(
        "sendMessage",
        data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"},
    )
    message_ids.append(result["message_id"])

    if os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as pdf:
            result = _post(
                "sendDocument",
                data={"chat_id": CHAT_ID, "caption": f"Resume for job `{job_id}`", "parse_mode": "Markdown"},
                files={"document": pdf},
            )
            message_ids.append(result["message_id"])

    if os.path.exists(cl_path):
        with open(cl_path, 'rb') as cl:
            result = _post(
                "sendDocument",
                data={"chat_id": CHAT_ID, "caption": f"Cover letter for job `{job_id}`", "parse_mode": "Markdown"},
                files={"document": cl},
            )
            message_ids.append(result["message_id"])

    return message_ids


def delete_telegram_messages(message_ids):
    deleted = 0
    for message_id in message_ids or []:
        try:
            _post("deleteMessage", data={"chat_id": CHAT_ID, "message_id": message_id})
            deleted += 1
        except Exception:
            continue
    return deleted


def fetch_updates(offset=None, timeout=30):
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    result = _post("getUpdates", params=params)
    return result


def send_text_message(text, reply_to_message_id=None):
    data = {"chat_id": CHAT_ID, "text": text}
    if reply_to_message_id is not None:
        data["reply_to_message_id"] = reply_to_message_id
    result = _post("sendMessage", data=data)
    return result["message_id"]


def set_bot_commands(commands):
    payload = {"commands": commands}
    return _post("setMyCommands", json=payload)
