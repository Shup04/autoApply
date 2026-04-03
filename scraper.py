import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# Load credentials from .env
load_dotenv()
USERNAME = os.getenv("TRU_USERNAME")
PASSWORD = os.getenv("TRU_PASSWORD")

def login_to_symplicity():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("Navigating to TRU Symplicity portal...")
        page.goto("https://tru-csm.symplicity.com/students/")

        # NOTE: If TRU requires clicking a "Student Login" button to reach an SSO page, 
        # we will need to add a page.click() step here first.
        
        try:
            print("Injecting credentials...")
            # These selectors are common for Symplicity, but we may need to adjust them
            page.fill("input[name='username']", USERNAME)
            page.fill("input[name='password']", PASSWORD)
            
            print("Clicking submit...")
            page.click("input[type='submit']") # or the specific button selector
            
        except Exception as e:
            print(f"Selector not found or page layout differs: {e}")

        # Holding the browser open so you can see if it worked
        print("Holding for 30 seconds to verify...")
        page.wait_for_timeout(30000) 

        browser.close()

if __name__ == "__main__":
    login_to_symplicity()
