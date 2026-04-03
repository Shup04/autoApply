import json
import os
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()
USERNAME = os.getenv("TRU_USERNAME")
PASSWORD = os.getenv("TRU_PASSWORD")

def fetch_details():
    if not os.path.exists("scraped_jobs.json"):
        print("Error: scraped_jobs.json not found.")
        return

    with open("scraped_jobs.json", "r") as f:
        jobs = json.load(f)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("Logging in to maintain session...")
        page.goto("https://tru-csm.symplicity.com/students/")
        page.fill("input[name='username']", USERNAME)
        page.fill("input[name='password']", PASSWORD)
        page.click("input[type='submit']")
        page.wait_for_timeout(3000)

        for job in jobs:
            print(f"Fetching: {job['title']}...")
            try:
                page.goto(job['url'], wait_until="domcontentloaded")
                
                # Target the exact TinyMCE container from your HTML
                selector = ".field-widget-tinymce"
                page.wait_for_selector(selector, timeout=5000)
                
                description = page.locator(selector).inner_text()
                job['full_description'] = description.strip()
                print("   [✓] Description saved.")
            except Exception as e:
                job['full_description'] = "Manual review required: Selector not found."
                print(f"   [!] Failed: {job['title']}")

        with open("jobs_with_descriptions.json", "w") as f:
            json.dump(jobs, f, indent=4)
        
        print(f"\nDone! Processed {len(jobs)} jobs.")
        browser.close()

if __name__ == "__main__":
    fetch_details()
