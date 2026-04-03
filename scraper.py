import os
import json
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# Load credentials from .env
load_dotenv()
USERNAME = os.getenv("TRU_USERNAME")
PASSWORD = os.getenv("TRU_PASSWORD")

def scrape_symplicity_jobs():
    with sync_playwright() as p:
        # Launching with a slow_mo of 50ms helps prevent race conditions on Arch
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context()
        page = context.new_page()

        print("1. Logging into TRU Symplicity...")
        page.goto("https://tru-csm.symplicity.com/students/")
        try:
            if USERNAME: page.fill("input[name='username']", USERNAME)
            if PASSWORD: page.fill("input[name='password']", PASSWORD)
            page.click("input[type='submit']")
        except Exception as e:
            print(f"   [!] Login error (may already be logged in): {e}")

        # Wait for dashboard
        page.wait_for_timeout(3000)

        print("2. Navigating to the Job Discovery board...")
        page.goto("https://tru-csm.symplicity.com/students/app/jobs/discover")
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(2000) 

        print("3. Opening 'More Filters'...")
        page.locator("button#cfEmployersAdvFiltersBtn").click()
        page.wait_for_timeout(1000) 

        print("4. Selecting Desired Majors...")
        # Click the placeholder div to wake up the search input
        trigger = page.locator("div.picklist-selected-text, .picklist-field").first
        trigger.click()
        
        major_input = page.locator("input[placeholder='Search']").first
        major_input.wait_for(state="visible", timeout=5000)

        print("   -> Searching for 'engineering' programs...")
        major_input.fill("") 
        major_input.press_sequentially("engineering", delay=100)
        page.wait_for_timeout(2000) 

        target_majors = [
            "Bachelor of Engineering",
            "BEng - Software Engineering",
            "BEng - Computer Engineering",
            "Electrical-Computer Engineering Transfer Program- 2nd yr",
            "Engineering Transfer Program"
        ]

        for major in target_majors:
            try:
                # We use .last because the search box often creates a duplicate 'pill' 
                option = page.get_by_text(major, exact=False).last
                if option.is_visible():
                    print(f"      + Checking: {major}")
                    option.click()
                    page.wait_for_timeout(300)
            except:
                continue

        print("5. Refining Filters...")
        # Check 'Omit All Majors' if it exists in the drawer
        try:
            omit_text = page.get_by_text("Omit All Majors", exact=False)
            if omit_text.is_visible():
                omit_text.click()
                print("   -> 'Omit All Majors' checked.")
        except: pass

        # Click the Apply button using the specific aria-label
        print("   -> Applying all filters...")
        page.locator("button[aria-label='Apply More Filters']").click()
        
        # Wait for the UI to refresh
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(4000)

        print("6. Scraping Job Cards...")
        all_jobs = []
        # Using the exact class found in the BenchSci HTML
        job_cards_locator = page.locator("div.list-item[role='link']")
        
        count = job_cards_locator.count()
        if count == 0:
            print("   [!] No jobs found matching these filters.")
            browser.close()
            return

        print(f"   -> Found {count} potential matches. Extracting details...")
        
        for i in range(count):
            try:
                # Refetch locator inside loop to avoid 'stale element' errors
                card = page.locator("div.list-item[role='link']").nth(i)
                
                # Preliminary check to skip 'All Majors' if the toggle failed
                card_text = card.inner_text().lower()
                if "all majors" in card_text:
                    continue

                # Extract Title and Company using the BenchSci specific spans
                title = card.locator(".list-item-title span").first.inner_text().strip()
                company = card.locator(".list-item-subtitle span").first.inner_text().strip()

                # Get the URL: Since there's no href, we click the card to update the browser URL
                card.click()
                page.wait_for_timeout(1500) # Wait for side-panel/page load
                
                job_url = page.url
                
                print(f"      [✓] Sniped: {title} @ {company}")
                
                all_jobs.append({
                    "title": title,
                    "company": company,
                    "url": job_url
                })

                # If clicking opens a full page, go back. 
                # If it opens a side-panel, clicking the next card will just swap them.
                if "/discover" not in page.url:
                    page.go_back()
                    page.wait_for_timeout(1000)

            except Exception as e:
                print(f"      [!] Error on card {i}: {e}")
                continue

        # Save to JSON
        with open("scraped_jobs.json", "w") as f:
            json.dump(all_jobs, f, indent=4)
            
        print(f"\nSuccess! Saved {len(all_jobs)} engineering jobs to scraped_jobs.json.")
        browser.close()

if __name__ == "__main__":
    scrape_symplicity_jobs()
