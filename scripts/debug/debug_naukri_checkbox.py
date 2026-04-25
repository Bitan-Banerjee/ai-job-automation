import os
import json
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')
TEST_URL = "https://www.naukri.com/job-listings-pyspark-developer-vipsa-talent-solutions-hyderabad-pune-bengaluru-3-to-6-years-240426031032"
COMPANY_NAME = "VIPSA_TALENT_SOLUTIONS"

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

        # Attempt to answer questions until we hit the checkbox
        for step in range(10):
            print(f"\\n--- Step {step + 1} ---")
            time.sleep(2)
            
            # Detect question
            question_els = page.locator(".chatbot_ListItem, .msg, .chipMsg, p, span")
            if question_els.count() == 0:
                print("❌ No question elements found.")
                break
            q_text = question_els.last.inner_text().strip()
            print(f"❓ Question: {q_text}")

            # If it's a text input (like years of experience)
            chat_input = page.locator('.textArea, [contenteditable="true"], input:not([type="hidden"]), textarea').first
            
            # If it's the city question, target "Bengaluru"
            if "city" in q_text.lower() or "relocate" in q_text.lower():
                target_ans = "Bengaluru"
                print(f"🎯 Target Answer (Checkbox): {target_ans}")
                
                # ENHANCED CHECKBOX CLICKING LOGIC
                clicked = page.evaluate("""([ans]) => {
                    const normalizedVal = ans.toLowerCase().trim();
                    
                    // Look for checkboxes and their labels
                    const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                    for (const cb of checkboxes) {
                        const wrapper = cb.closest('label') || cb.parentElement;
                        if (wrapper && wrapper.innerText.toLowerCase().includes(normalizedVal)) {
                            console.log("Found checkbox wrapper:", wrapper);
                            wrapper.scrollIntoView({block: 'center'});
                            
                            // Try clicking the wrapper
                            wrapper.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
                            wrapper.dispatchEvent(new PointerEvent('pointerup', {bubbles: true}));
                            wrapper.click();
                            
                            // Also try checking the input directly just in case
                            cb.checked = true;
                            cb.dispatchEvent(new Event('change', {bubbles: true}));
                            
                            wrapper.style.border = "2px solid red";
                            return true;
                        }
                    }
                    
                    // Fallback to text matching on typical option containers
                    const targets = Array.from(document.querySelectorAll('.chatbot_Drawer .chipMsg, .pill, label, .option, button, span, .chatbot_ListItem'));
                    const match = targets.find(t => t.innerText.trim().toLowerCase() === normalizedVal);
                    
                    if (match) {
                        console.log("Found text match:", match);
                        match.scrollIntoView({block: 'center'});
                        match.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
                        match.dispatchEvent(new PointerEvent('pointerup', {bubbles: true}));
                        match.click();
                        match.style.border = "2px solid red";
                        return true;
                    }
                    return false;
                }""", [target_ans])
                
                if clicked:
                    print(f"✅ Executed enhanced click on '{target_ans}'")
                else:
                    print(f"❌ Failed to find/click '{target_ans}'")
                    
            elif chat_input.is_visible():
                target_ans = "4"
                print(f"🎯 Target Answer (Text): {target_ans}")
                page.evaluate("""([ans]) => {
                    const input = document.querySelector('.textArea, [contenteditable="true"], .chatbot_Drawer input:not([type="hidden"]), .chatbot_Drawer textarea');
                    if (input) {
                        input.focus();
                        if (input.tagName === 'INPUT' || input.tagName === 'TEXTAREA') { input.value = ans; }
                        else { input.innerText = ans; }
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""", [target_ans])
            else:
                print("❌ No input method found for this question.")
                break

            time.sleep(2)
            take_screenshot(page, f"3_after_ans_step_{step}")
            
            # Click Save/Submit
            submit_btn = page.locator(".sendMsg, .sendMsgbtn_container, .chatBot-ic-send, button:has-text('Save'), button:has-text('Submit'), button:has-text('Next')").last
            if submit_btn.is_visible():
                submit_btn.click(force=True)
                print("📨 Clicked Save/Submit")
                time.sleep(4)
            else:
                print("❌ Save/Submit button not found.")
                break
                
            # Check if we are done or if question changed
            if page.locator("button:has-text('Applied'), [class*='applied' i]").is_visible():
                 print("✅ Application successfully submitted!")
                 take_screenshot(page, "4_final_success")
                 break

        input("Press Enter to close browser...")
        browser.close()

if __name__ == "__main__":
    debug_apply()
