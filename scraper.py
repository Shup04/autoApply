from playwright.sync_api import sync_playwright
import time

def test_symplicity_login():
    with sync_playwright() as p:
        # headless=False allows you to visually see what the bot is doing
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("Navigating to TRU Symplicity portal...")
        page.goto("https://tru-csm.symplicity.com/students/")

        # Pausing execution so you can manually inspect the login fields
        print("Page loaded. Holding for 30 seconds...")
        time.sleep(30)

        print("Closing browser...")
        browser.close()

if __name__ == "__main__":
    test_symplicity_login()
