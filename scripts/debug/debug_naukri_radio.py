import os
import json
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')
TEST_URL = "https://www.naukri.com/job-listings-data-engineer-swarnasky-technologies-hyderabad-4-to-6-years-210426041059"
COMPANY_NAME = "Swarnasky_Technologies"

def take_screenshot(page, name):
    ss_dir = os.path.join(BASE_DIR, 'logs', 'debug_screenshots')
    os.makedirs(ss_dir, exist_ok=True)
    path = os.path.join(ss_dir, f"{name}.png")
    page.screenshot(path=path)
    print(f"📸 Screenshot: {path}")

def debug_apply():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f:
                context.add_cookies(json.load(f))
        
        page = context.new_page()
        print(f"🚀 Navigating to: {TEST_URL}")
        page.goto(TEST_URL)
        time.sleep(5)
        
        take_screenshot(page, "1_initial_page")

        apply_btn = page.locator("button:has-text('Apply'), [class*='applyBtn' i]").first
        if apply_btn.is_visible():
            apply_btn.click()
            print("🔘 Clicked Apply.")
            time.sleep(8)
            take_screenshot(page, "2_form_opened")
        else:
            print("❌ Apply button not found.")
            return

        # Attempt to answer ONE question as a test
        print("🔍 Detecting question...")
        
        # Aggressive selector for question text
        question_el = page.locator(".chatbot_ListItem, .msg, .chipMsg, p, span").last
        q_text = question_el.inner_text().strip()
        print(f"❓ Question: {q_text}")

        # Targeted logic for radio-style options
        target_ans = "Yes"
        print(f"🎯 Target Answer: {target_ans}")

        # NEW AGGRESSIVE CLICKING LOGIC
        clicked = page.evaluate("""([ans]) => {
            const normalizedVal = ans.toLowerCase().trim();
            const targets = Array.from(document.querySelectorAll('.chatbot_Drawer .chipMsg, .pill, label, .option, button, span, .chatbot_ListItem'));
            const match = targets.find(t => t.innerText.trim().toLowerCase() === normalizedVal);
            
            if (match) {
                console.log("Found match, triggering events...");
                // 1. Dispatch pointer events (Modern Frameworks)
                match.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
                match.dispatchEvent(new PointerEvent('pointerup', {bubbles: true}));
                // 2. Standard Click
                match.click();
                // 3. Verify visual change (Optional: add a border to debug)
                match.style.border = "2px solid red";
                return true;
            }
            return false;
        }""", [target_ans])

        if clicked:
            print(f"✅ Executed aggressive click on '{target_ans}'")
            time.sleep(2)
            take_screenshot(page, "3_after_click_verification")
            
            # Click Save/Submit
            submit_btn = page.locator(".sendMsg, .sendMsgbtn_container, .chatBot-ic-send, button:has-text('Save'), button:has-text('Submit')").last
            if submit_btn.is_visible():
                submit_btn.click(force=True)
                print("📨 Clicked Save/Submit")
                time.sleep(5)
                take_screenshot(page, "4_after_submit")
                
                # Check if question changed
                new_q_text = page.locator(".chatbot_ListItem, .msg, .chipMsg, p, span").last.inner_text().strip()
                if new_q_text != q_text:
                    print(f"🎊 Success! Question changed to: {new_q_text}")
                else:
                    print("❌ Failure: Question did not change. Still on the same step.")
            else:
                print("❌ Save/Submit button not found.")
        else:
            print(f"❌ Target answer '{target_ans}' element not found.")

        input("Press Enter to close browser...")
        browser.close()

if __name__ == "__main__":
    debug_apply()
