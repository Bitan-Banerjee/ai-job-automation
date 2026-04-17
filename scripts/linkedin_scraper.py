import os
import json
import random
import time
import argparse
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from datetime import datetime

# Path setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

EMAIL = os.getenv("LINKEDIN_EMAIL")
PASSWORD = os.getenv("LINKEDIN_PASSWORD")
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'linkedin_session.json')
JOBS_FILE = os.path.join(BASE_DIR, 'data', 'jobs.json')
SEEN_JOBS_FILE = os.path.join(BASE_DIR, 'data', 'seen_jobs.json')

def human_delay(min_sec=1.5, max_sec=4.5):
    time.sleep(random.uniform(min_sec, max_sec))

def safe_goto(page, url, timeout=60000):
    """Attempt to go to a URL with a longer timeout and a single retry."""
    try:
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
    except Exception as e:
        print(f"  ⚠️ Timeout on {url}. Retrying once...")
        time.sleep(5)
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")

def dismiss_login_popup(page):
    try:
        page.keyboard.press("Escape")
        dismiss_btn = page.query_selector("button[aria-label='Dismiss']")
        if dismiss_btn: dismiss_btn.click(timeout=1000)
    except: pass

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return {}

def slow_scroll(page, scrolls=10):
    for i in range(scrolls):
        dismiss_login_popup(page)
        scroll_amount = random.randint(300, 600)
        page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        time.sleep(random.uniform(1.0, 2.5))
    return page.query_selector_all(".job-card-container")

def scrape_linkedin_jobs(keyword, location, max_pages, max_jobs):
    seen_jobs = load_seen_jobs()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "r") as f:
                context.add_cookies(json.load(f))
        
        page = context.new_page()
        # Set a global default timeout of 60s instead of 30s
        page.set_default_timeout(60000)

        print("🌐 Opening LinkedIn...")
        safe_goto(page, "https://www.linkedin.com/login")
        
        if page.query_selector("#username"):
            print("🔐 Session expired. Logging in...")
            page.fill("#username", EMAIL)
            page.fill("#password", PASSWORD)
            page.click('[type="submit"]')
            page.wait_for_timeout(5000)
            with open(SESSION_FILE, "w") as f:
                json.dump(context.cookies(), f)

        all_jobs = []
        for page_num in range(max_pages):
            if len(all_jobs) >= max_jobs: break
            
            start = page_num * 25
            url = f"https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}&f_AL=true&start={start}"
            print(f"📄 Scraping Page {page_num + 1}...")
            
            safe_goto(page, url)
            human_delay(3, 5)
            job_cards = slow_scroll(page)
            
            for card in job_cards:
                if len(all_jobs) >= max_jobs: break
                try:
                    title_el = card.query_selector(".job-card-list__title--link span[aria-hidden='true']")
                    if not title_el: continue
                    title = title_el.inner_text().strip()
                    
                    subtitle = card.query_selector(".artdeco-entity-lockup__subtitle")
                    company = subtitle.inner_text().strip() if subtitle else "Unknown"
                    
                    link_el = card.query_selector(".job-card-list__title--link")
                    href = link_el.get_attribute("href")
                    job_url = "https://www.linkedin.com" + href.split("?")[0]

                    if job_url in seen_jobs: continue
                    
                    card.click()
                    human_delay(2, 4)
                    
                    # Wait specifically for the description to appear
                    page.wait_for_selector(".jobs-description", timeout=10000)
                    description = page.query_selector(".jobs-description").inner_text().strip()
                    
                    all_jobs.append({
                        "title": title, 
                        "company": company, 
                        "url": job_url, 
                        "description": description[:1200]
                    })
                    
                    seen_jobs[job_url] = {"title": title, "company": company, "seen_at": datetime.now().isoformat()}
                    print(f"  ✅ Scraped: {title} at {company}")
                except Exception as e:
                    continue

        os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)
        with open(JOBS_FILE, "w") as f:
            json.dump({"jobs": all_jobs}, f, indent=2)
        with open(SEEN_JOBS_FILE, "w") as f:
            json.dump(seen_jobs, f, indent=2)
            
        browser.close()
        print(f"💾 Done! Scraped {len(all_jobs)} jobs.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape LinkedIn job postings.")
    parser.add_argument("--pages", type=int, default=1, help="Number of search result pages to scrape.")
    parser.add_argument("--max", type=int, default=10, help="Maximum number of jobs to scrape in total.")
    args = parser.parse_args()
    
    scrape_linkedin_jobs(keyword="Data Engineer", location="India", max_pages=args.pages, max_jobs=args.max)
