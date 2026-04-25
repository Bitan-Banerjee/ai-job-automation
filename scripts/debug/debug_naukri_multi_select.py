import os
import json
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')
TEST_URL = "https://www.naukri.com/job-listings-data-engineer-exl-gurugram-bengaluru-2-to-5-years-210426000116"

def take_screenshot(page, name):
    ss_dir = os.path.join(BASE_DIR, 'logs', 'debug_screenshots')
    os.makedirs(ss_dir, exist_ok=True)
    path = os.path.join(ss_dir, f"{name}.png")
    page.screenshot(path=path)
    print(f"📸 Screenshot: {path}")

def debug_apply():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        context = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent=user_agent,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Referer": "https://www.google.com/"
            }
        )
        
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

        for step in range(15):
            print(f"\n--- Step {step + 1} ---")
            
            # Use the more robust extraction logic
            questions = page.evaluate("""() => {
                const results = [];
                const drawer = document.querySelector('.chatbot_DrawerContentWrapper') || 
                               document.querySelector('.chatbot_MessageContainer') || 
                               document.querySelector('[role="dialog"]');
                if (!drawer) return { error: "No drawer found", html: document.body.innerHTML.substring(0, 1000) };

                const messageEls = Array.from(drawer.querySelectorAll('.chatbot_ListItem, .msg, .chipMsg, p, span'));
                let chatbotQuestion = "";
                for (let i = messageEls.length - 1; i >= 0; i--) {
                    const text = messageEls[i].innerText.trim();
                    if (text.length > 10 && !text.includes('logo') && !text.includes('Naukri') && !text.includes('Save')) {
                        chatbotQuestion = text;
                        break;
                    }
                }

                if (!chatbotQuestion) {
                    return { error: "No question text found", messageCount: messageEls.length };
                }

                // Look for options
                const optionEls = Array.from(drawer.querySelectorAll('.chipMsg, .pill, .option, [class*="chip" i], [class*="pill" i], label, input[type="checkbox"], input[type="radio"]'));
                const options = optionEls.map(o => {
                    const text = o.innerText.trim() || (o.nextSibling ? o.nextSibling.textContent.trim() : "") || o.getAttribute('value') || "";
                    return { text, tagName: o.tagName, className: o.className, id: o.id };
                }).filter(o => o.text.length > 0 && o.text.length < 100 && o.text !== chatbotQuestion && !o.text.includes('Save'));

                // Look for text input
                const chatInput = drawer.querySelector('.textArea, [contenteditable="true"], input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), textarea');
                
                return {
                    question: chatbotQuestion,
                    options: options,
                    hasInput: !!chatInput,
                    inputType: chatInput ? chatInput.tagName : null
                };
            }""")

            if "error" in questions:
                print(f"⚠️ Extraction Error: {questions['error']}")
                if "messageCount" in questions:
                    print(f"   Message count: {questions['messageCount']}")
                break

            print(f"❓ Question: {questions['question']}")
            if questions['options']:
                print(f"📋 Options: {[o['text'] for o in questions['options']]}")
            
            target_ans = None
            if "city" in questions['question'].lower() or "relocate" in questions['question'].lower():
                target_ans = "Bengaluru"
            elif "experience" in questions['question'].lower() or "years" in questions['question'].lower():
                target_ans = "4"
            
            if not target_ans:
                if questions['options']:
                    target_ans = questions['options'][0]['text']
                elif questions['hasInput']:
                    target_ans = "Yes" # Default fallback
                else:
                    print("❌ Could not determine answer.")
                    break

            print(f"🎯 Target Answer: {target_ans}")

            if questions['options']:
                # Click logic for options (including checkboxes)
                clicked = page.evaluate("""([ans]) => {
                    const normalizedVal = ans.toLowerCase().trim();
                    const drawer = document.querySelector('.chatbot_DrawerContentWrapper') || 
                                   document.querySelector('.chatbot_MessageContainer') || 
                                   document.querySelector('[role="dialog"]');
                    
                    // Priority 1: Checkboxes
                    const checkboxes = Array.from(drawer.querySelectorAll('input[type="checkbox"]'));
                    for (const cb of checkboxes) {
                        const label = cb.closest('label') || cb.parentElement;
                        if (label && label.innerText.toLowerCase().includes(normalizedVal)) {
                            console.log("Clicking checkbox label:", label.innerText);
                            label.click();
                            return true;
                        }
                    }

                    // Priority 2: Generic matches
                    const targets = Array.from(drawer.querySelectorAll('.chipMsg, .pill, label, .option, button, span, .chatbot_ListItem'));
                    const match = targets.find(t => t.innerText.trim().toLowerCase() === normalizedVal);
                    if (match) {
                        console.log("Clicking generic match:", match.innerText);
                        match.scrollIntoView({block: 'center'});
                        match.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
                        match.dispatchEvent(new PointerEvent('pointerup', {bubbles: true}));
                        match.click();
                        return true;
                    }
                    return false;
                }""", [target_ans])
                if clicked:
                    print(f"✅ Clicked '{target_ans}'")
                else:
                    print(f"❌ Failed to click '{target_ans}'")
            elif questions['hasInput']:
                # Fill logic for text inputs
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
                print(f"✍️ Filled '{target_ans}'")

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
            
            # Success check
            if page.locator("button:has-text('Applied'), [class*='applied' i]").is_visible():
                 print("✅ Application successfully submitted!")
                 take_screenshot(page, "4_final_success")
                 break

        input("Press Enter to close browser...")
        browser.close()

if __name__ == "__main__":
    debug_apply()
