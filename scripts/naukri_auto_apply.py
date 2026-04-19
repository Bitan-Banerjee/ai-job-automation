import os
import json
import time
import random
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATCHED_PATH = os.path.join(BASE_DIR, 'data', 'matched_jobs.json')
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')

def naukri_apply(matched_path=MATCHED_PATH):
    if not os.path.exists(matched_path):
        print("❌ No matched jobs found to apply to.")
        return
        
    with open(matched_path, 'r') as f:
        jobs = json.load(f).get("approved_jobs", [])
        
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f: 
                context.add_cookies(json.load(f))
                
        page = context.new_page()
        page.set_default_timeout(60000)
        
        for job in jobs:
            score = job.get('ai_score', 0)
            print(f"\n🚀 Processing Naukri Job: {job.get('company', 'Unknown')} (Score: {score})")
            
            try:
                page.goto(job['url'], wait_until="domcontentloaded")
                time.sleep(random.uniform(2, 4))
                
                # Check if already applied on Naukri
                if page.locator("text='Already Applied'").is_visible() or page.locator("text='Applied'").is_visible():
                    print(f"  ✅ Already applied to {job['company']}. Skipping.")
                    continue
                    
                # Hunt for the standard Apply button
                apply_btn = page.locator("button:has-text('Apply'), a:has-text('Apply'), #apply-button").first
                if apply_btn.is_visible(timeout=5000):
                    apply_btn.click()
                    print("    🔘 Clicked Apply button")
                    time.sleep(3) # Wait for confirmation toast or redirect
                    
                    print(f"  ✅ SUCCESS! Application fully submitted on Naukri.")
                    job['status'] = 'applied'
                    
                    with open(matched_path, 'w') as f:
                        json.dump({"approved_jobs": jobs}, f, indent=4)
                else:
                    print("  ❌ Apply button not found. Moving on.")
            except Exception as e:
                error_msg = str(e).split('\n')[0]
                print(f"  ⚠️ Failed to apply: {error_msg}")
                
        browser.close()