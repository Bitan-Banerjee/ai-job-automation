import os
import json
import time
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILED_PATH = os.path.join(BASE_DIR, 'data', 'failed_applications.json')
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')

if not os.path.exists(FAILED_PATH):
    print("❌ No failed_applications.json found.")
    exit()

with open(FAILED_PATH, 'r') as f:
    failed_jobs = json.load(f).get('failed_jobs', [])

naukri_jobs = [j for j in failed_jobs if 'naukri.com' in j.get('url', '')]

if not naukri_jobs:
    print("❌ No failed Naukri jobs found.")
    exit()

target_job = naukri_jobs[0]
print(f"🎯 Debugging: {target_job.get('company')} — {target_job.get('url')}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={'width': 1440, 'height': 900},
        user_agent=(
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'
        )
    )

    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, 'r') as f:
            context.add_cookies(json.load(f))

    page = context.new_page()
    page.set_default_timeout(60000)
    page.goto(target_job['url'], wait_until="domcontentloaded")
    time.sleep(4)

    # Click Apply
    apply_btn = page.locator(
        "button:has-text('Apply'), a:has-text('Apply'), #apply-button"
    ).first
    if not apply_btn.is_visible(timeout=5000):
        print("❌ Apply button not visible.")
        browser.close()
        exit()

    apply_btn.click()
    print("🔘 Clicked Apply. Waiting 8s for panel...")
    time.sleep(8)

    # Dump panel HTML
    panel_html = page.evaluate("""() => {
        const selectors = [
            "[role='dialog']",
            "[class*='drawer' i]",
            "[class*='slideIn' i]",
            "[class*='rightPanel' i]",
            "[class*='applyModal' i]",
            "[class*='chatbot' i]",
            "[class*='bChatWrap' i]",
            "[class*='modal' i]",
            "[class*='overlay' i]",
            "[class*='popup' i]",
        ];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.offsetWidth > 0) {
                return { selector: sel, html: el.outerHTML.slice(0, 8000) };
            }
        }
        return { selector: 'body_fallback', html: document.body.outerHTML.slice(0, 8000) };
    }""")

    print(f"\n✅ Matched panel selector: {panel_html['selector']}")
    print(f"\n--- PANEL HTML ---")
    print(panel_html['html'][:3000])

    logs_dir = os.path.join(BASE_DIR, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    out_path = os.path.join(logs_dir, 'panel_debug.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(panel_html['html'])
    print(f"\n📄 Saved to: {out_path}")

    input("\n👀 Browser open — inspect manually too. Press Enter to close...")
    browser.close()