import requests
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_package():
    # 1. Base Setup (Define these at the top so they always exist)
    base_url = f"https://api.telegram.org/bot{TOKEN}"
    doc_url = f"{base_url}/sendDocument"
    msg_url = f"{base_url}/sendMessage"
    
    # 2. File Paths (Updated to match your actual files with the '1' suffix)
    resume_path = "Resume_Schmidt_BenchSci1.pdf"
    cl_path = "CL_Schmidt_BenchSci.txt"

    print(f"🤖 Searching for: {resume_path} and {cl_path}")

    # 3. Send Text Notification
    msg_payload = {
        "chat_id": CHAT_ID, 
        "text": "🎯 *Sniper Alert:* Testing BenchSci document delivery.",
        "parse_mode": "Markdown"
    }
    requests.post(msg_url, data=msg_payload)

    # 4. Send the PDF Resume
    if os.path.exists(resume_path):
        with open(resume_path, "rb") as resume_file:
            r = requests.post(doc_url, data={"chat_id": CHAT_ID}, files={"document": resume_file})
            print(f"✅ Resume sent: {r.status_code}")
    else:
        print(f"❌ Error: {resume_path} not found. Check the filename!")

    # 5. Send the Cover Letter
    if os.path.exists(cl_path):
        with open(cl_path, "rb") as cl_file:
            r = requests.post(doc_url, data={"chat_id": CHAT_ID}, files={"document": cl_file})
            print(f"✅ Cover Letter sent: {r.status_code}")
    else:
        print(f"❌ Error: {cl_path} not found.")

if __name__ == "__main__":
    send_package()
