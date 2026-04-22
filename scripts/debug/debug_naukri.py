import os
import json
import time
import sys
import re
from playwright.sync_api import sync_playwright

# Add scripts folder to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')
FAILED_PATH = os.path.join(BASE_DIR, 'data', 'failed_applications.json')

# Jobs to verify and clean
VERIFY_URLS = [
    "https://www.naukri.com/job-listings-python-software-developer-bounteous-x-accolite-gurugram-bengaluru-4-to-9-years-190426004124",
    "https://www.naukri.com/job-listings-data-engineer-falcon-services-kochi-6-to-11-years-210426009549"
]

def check_success(page):
    """Refined detection for already applied state."""
    applied_btn = page.locator("button:has-text('Applied'), [class*='applied' i]").first
    if applied_btn.is_visible(timeout=5000):
        return True, "Green 'Applied' button detected"
    
    success_keys = ["successfully applied", "application submitted", "already applied", "applied on"]
    body_text = page.evaluate("() => document.body.innerText.toLowerCase()")
    for k in success_keys:
        if k in body_text:
            return True, f"Success text: '{k}'"
            
    return False, "Not applied"

def load_and_fix_failed_json(path):
    """Thoroughly sanitizes the failed jobs JSON before loading."""
    if not os.path.exists(path): return {"failed_jobs": []}
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # 1. Strip // comments
    content = re.sub(r'//.*', '', content)
    # 2. Fix missing commas between objects (greedy regex)
    content = re.sub(r'}\s*{', '}, {', content)
    # 3. Fix trailing commas before closing brackets
    content = re.sub(r',\s*]', ']', content)
    content = re.sub(r',\s*}', '}', content)
    
    try:
        return json.loads(content, strict=False)
    except json.JSONDecodeError as e:
        print(f"❌ JSON Still Corrupt: {e}")
        # Final fallback: manual extraction via regex if json.loads fails
        return None

def debug_state_sync():
    data = load_and_fix_failed_json(FAILED_PATH)
    if not data:
        print("🛑 Critical: Cannot parse failed_applications.json. Update manually required.")
        return

    failed_jobs = data.get('failed_jobs', [])
    urls_to_remove = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f: context.add_cookies(json.load(f))
        
        page = context.new_page()

        for url in VERIFY_URLS:
            print(f"🔍 Checking: {url}")
            page.goto(url, wait_until="domcontentloaded")
            time.sleep(4)

            is_applied, reason = check_success(page)
            if is_applied:
                print(f"✅ VERIFIED APPLIED: {reason}")
                urls_to_remove.append(url)
            else:
                print(f"❌ NOT APPLIED: {reason}")

        browser.close()

    # --- PERSIST STATE ---
    if urls_to_remove:
        initial_len = len(failed_jobs)
        new_failed = [j for j in failed_jobs if j.get('url') not in urls_to_remove]
        
        data['failed_jobs'] = new_failed
        with open(FAILED_PATH, 'w') as f:
            json.dump(data, f, indent=4)
        
        print(f"📝 STATE SYNCED: Removed {len(urls_to_remove)} jobs from failed list. ({initial_len} -> {len(new_failed)})")
    else:
        print("ℹ️ No state changes needed.")

if __name__ == "__main__":
    debug_state_sync()
