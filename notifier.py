import requests
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_job_alert(job_title, company, url, pdf_path, cl_path):
    # 1. Send the text alert
    message = f"🎯 *New Job Found!*\n\n*Title:* {job_title}\n*Company:* {company}\n\n[View Posting]({url})"
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                  data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"})

    # 2. Send the PDF Resume
    if os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as pdf:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendDocument", 
                          data={"chat_id": CHAT_ID}, files={"document": pdf})

    # 3. Send the Cover Letter PDF
    if os.path.exists(cl_path):
        with open(cl_path, 'rb') as cl:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendDocument", 
                          data={"chat_id": CHAT_ID}, files={"document": cl})
