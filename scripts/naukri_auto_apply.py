import os
import json
import time
import random
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

try:
    from auto_apply import get_batch_answers_from_gemini, REGISTRY_PATH
except ImportError:
    REGISTRY_PATH = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATCHED_PATH = os.path.join(BASE_DIR, 'data', 'matched_jobs.json')
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')
REGISTRY_PATH = os.path.join(BASE_DIR, 'data', 'naukri_qa_registry.json')


def get_registry():
    if not os.path.exists(REGISTRY_PATH): return {}
    with open(REGISTRY_PATH, 'r') as f: return json.load(f)


def save_registry(registry):
    with open(REGISTRY_PATH, 'w') as f: json.dump(registry, f, indent=4)


def take_screenshot(page, company_name, error_type):
    """Saves a timestamped screenshot to logs/screenshots/ for debugging."""
    try:
        now = datetime.now()
        ss_dir = os.path.join(BASE_DIR, 'logs', 'screenshots', now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))
        os.makedirs(ss_dir, exist_ok=True)
        
        safe_company = re.sub(r'[^\w\s-]', '', company_name).strip().replace(' ', '_')
        filename = f"{now.strftime('%H-%M-%S')}_naukri_{safe_company}_{error_type}.png"
        path = os.path.join(ss_dir, filename)
        
        page.screenshot(path=path)
        print(f"    📸 Screenshot saved: logs/screenshots/.../{filename}")
    except Exception as e:
        print(f"    ⚠️ Failed to take screenshot: {e}")


def detect_form_panel(page):
    """Refined detection for Naukri's drawer or chatbot form."""
    try:
        selectors = [
            ".chatbot_DrawerContentWrapper",
            ".chatbot_Drawer",
            "[class*='applyModal' i]",
            "[class*='questionnaire' i]",
            "[role='dialog']"
        ]
        for sel in selectors:
            panel = page.locator(sel).first
            if panel.is_visible(timeout=3000):
                # Ensure it's a real form (has inputs or is a known chatbot drawer)
                has_input = panel.locator("input, textarea, .textArea, [contenteditable='true'], .chipMsg, .pill").count() > 0
                if has_input or "chatbot" in sel.lower():
                    return True
        return False
    except: return False


def extract_questions(page):
    """Refined extraction logic for Naukri Chatbots and standard forms."""
    return page.evaluate("""() => {
        const questions = [];
        const drawer = document.querySelector('.chatbot_DrawerContentWrapper') || 
                       document.querySelector('.chatbot_MessageContainer') || 
                       document.querySelector('[role="dialog"]');
        if (!drawer) return [];

        // 1. CHATBOT MESSAGE EXTRACTION
        const messageEls = Array.from(drawer.querySelectorAll('.chatbot_ListItem, .msg, .chipMsg, p, span'));
        let chatbotQuestion = "";
        for (let i = messageEls.length - 1; i >= 0; i--) {
            const text = messageEls[i].innerText.trim();
            if (text.length > 10 && !text.includes('logo') && !text.includes('Naukri') && !text.includes('Save')) {
                chatbotQuestion = text;
                break;
            }
        }

        // 2. PILLS/OPTIONS (Only look near the end of the conversation to avoid stale options)
        const allItems = Array.from(drawer.querySelectorAll('.chatbot_ListItem, .chatbot_MessageContainer > div'));
        const lastFewItems = allItems.slice(-3); 
        let options = [];
        lastFewItems.forEach(item => {
            const found = Array.from(item.querySelectorAll('.chipMsg, .pill, .option, [class*="chip" i], [class*="pill" i], label, .ssrc__label, .optionVal, .chatbot_Chip'))
                .map(o => o.innerText.trim())
                .filter(t => t.length > 0 && t.length < 50 && t !== chatbotQuestion && !t.includes('Save') && !t.includes('Type here'));
            found.forEach(f => { if(!options.includes(f)) options.push(f); });
        });

        if (chatbotQuestion && options.length > 0) {
            questions.push({
                question: chatbotQuestion,
                type: 'styled_radio',
                options: options.map(o => ({ value: o, text: o })),
                index: 0
            });
        }

        // 3. INPUTS (If no pills)
        if (questions.length === 0 && chatbotQuestion) {
            const chatInput = drawer.querySelector('.textArea, [contenteditable="true"], input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]), textarea');
            if (chatInput) {
                questions.push({
                    question: chatbotQuestion,
                    type: chatInput.tagName === 'INPUT' || chatInput.tagName === 'TEXTAREA' ? 'text' : 'contenteditable',
                    options: [],
                    index: 0
                });
            }
        }

        // 4. FALLBACK: Standard Modal
        if (questions.length === 0) {
            const containers = Array.from(drawer.querySelectorAll('[class*="question" i], [class*="formItem" i], [class*="field" i]'));
            containers.forEach((container, idx) => {
                const labelEl = container.querySelector('label, [class*="label" i], p');
                const label = labelEl ? labelEl.innerText.trim() : container.innerText.split('\\n')[0].trim();
                if (label.length < 5) return;
                const hasInput = container.querySelector('input, textarea');
                if (hasInput) questions.push({ question: label, type: 'text', options: [], index: idx });
            });
        }
        return questions;
    }""")


def answer_questions(page, questions, registry):
    """Answer questions with aggressive click logic and modern event dispatching."""
    for q in questions:
        q_text = q['question']
        options = [o['text'] for o in q.get('options', [])]
        full_key = f"{q_text} (Options: {', '.join(options)})" if options else q_text
        print(f"    ❓ Question: {q_text[:80]}")

        if full_key not in registry:
            try:
                new_ans = get_batch_answers_from_gemini([full_key], registry)
                if new_ans: registry.update(new_ans); save_registry(registry)
            except: pass
        
        ans = str(registry.get(full_key, "")).strip()
        if not ans and options: ans = options[0]
        print(f"    💡 Answer: {ans}")

        if q['type'] in ('text', 'contenteditable'):
            # Use Playwright's native typing for better reliability
            input_locator = page.locator('.textArea, [contenteditable="true"], .chatbot_Drawer input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]), .chatbot_Drawer textarea').first
            if input_locator.is_visible():
                input_locator.click()
                time.sleep(0.5)
                # Clear existing text
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(ans, delay=50)
                time.sleep(0.5)
                # Dispatch events as fallback
                page.evaluate("""([ans]) => {
                    const input = document.querySelector('.textArea, [contenteditable="true"], .chatbot_Drawer input, .chatbot_Drawer textarea');
                    if (input) {
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""", [ans])
        elif q['type'] == 'styled_radio':
            # AGGRESSIVE CLICKING LOGIC (Verified for TCS/Wipro circle radios)
            page.evaluate("""([ans]) => {
                const normalizedVal = ans.toLowerCase().trim();
                const drawer = document.querySelector('.chatbot_DrawerContentWrapper');
                
                // Priority list of selectors for options
                const selectors = ['.ssrc__label', '.chipMsg', '.pill', 'label', '.option', 'button', 'span', '.chatbot_ListItem', '.chatbot_Chip', '.optionVal', '.singleselect-radiobutton-container div'];
                const targets = Array.from(drawer.querySelectorAll(selectors.join(',')));
                
                // Fuzzy matching: Exact match or includes
                const match = targets.find(t => {
                    const text = t.innerText.trim().toLowerCase();
                    if (!text) return false;
                    return text === normalizedVal || text.includes(normalizedVal) || normalizedVal.includes(text);
                });
                
                if (match) {
                    match.scrollIntoView({behavior: 'instant', block: 'center', inline: 'nearest'});
                    
                    // Force drawer scroll if match still hidden
                    const drawerContainer = document.querySelector('.chatbot_DrawerContentWrapper') || drawer;
                    if (drawerContainer) {
                        const rect = match.getBoundingClientRect();
                        const containerRect = drawerContainer.getBoundingClientRect();
                        if (rect.bottom > containerRect.bottom || rect.top < containerRect.top) {
                            match.scrollIntoView();
                        }
                    }
                    
                    // 1. Try to find and click actual radio input
                    const container = match.closest('li, div, label') || match.parentElement;
                    const radio = container.querySelector('input[type="radio"], input[type="checkbox"], .ssrc__radio');
                    
                    if (radio) {
                        radio.checked = true;
                        // Sequence of events to trigger React/Angular listeners
                        radio.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                        radio.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                        radio.click();
                        radio.dispatchEvent(new Event('change', {bubbles: true}));
                    } else {
                        // 2. Click the text element itself with events
                        match.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                        match.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                        match.click();
                    }
                    return true;
                }
                return false;
            }""", [ans])
        time.sleep(3) # Increase wait for bot state sync


def submit_form(page):
    """Submit current step with enhanced state checking."""
    try:
        # Target the container or the button itself
        save_btn = page.locator(".sendMsgbtn_container .send, button:has-text('Save'), button:has-text('Submit'), button:has-text('Next'), button:has-text('Apply'), .chatBot-ic-send").last
        
        if not save_btn.is_visible(timeout=3000):
            print("    ℹ️ No Save button visible. Chatbot might have auto-submitted.")
            return True

        is_disabled = page.evaluate("""(el) => {
            if (!el) return false;
            return el.classList.contains('disabled') || el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true';
        }""", save_btn.element_handle())
        
        if not is_disabled:
            save_btn.click(force=True)
            print("    📨 Clicked Save/Submit")
            time.sleep(4)
            return True
        else:
            print("    ⚠️ Save button is DISABLED. Trying to click child .sendMsg or pressing Enter.")
            inner_send = save_btn.locator(".sendMsg")
            if inner_send.count() > 0:
                inner_send.click(force=True)
                print("    📨 Clicked inner .sendMsg")
                time.sleep(4)
                return True
            else:
                page.keyboard.press("Enter")
                time.sleep(4)
                return True
    except Exception as e:
        print(f"    ⚠️ Submit failed: {e}")
        return False


def check_success(page):
    """Comprehensive success verification."""
    keys = [
        "successfully applied", "application submitted", "applied successfully", 
        "already applied", "thank you for showing interest", "application sent", 
        "applied on", "applied today", "thank you for applying", "all the best",
        "recruiter will get back to you", "interest has been sent"
    ]
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    if any(k in body for k in keys): return True
    
    # Check for buttons that indicate already applied state
    applied_btn = page.locator("button:has-text('Applied'), [class*='applied' i], .applied-btn").first
    if applied_btn.count() > 0:
        return applied_btn.is_visible(timeout=3000)
    return False


def is_expired(page):
    """Check if the job posting has expired."""
    title = page.title().lower()
    # Naukri redirects expired jobs to generic "Jobs In India" or search pages
    if "jobs in india" in title and "job vacancies" in title:
        print("    🔍 Expiry detected via generic redirect title.")
        return True

    expired_keys = ["this job has expired", "job is no longer available", "post is no longer available", "no longer taking applications", "not taking any more applications", "deactivated", "closed"]
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    found_text = [k for k in expired_keys if k in body]
    if found_text:
        print(f"    🔍 Expiry detected via keywords: {found_text}")
    
    banner_exists = page.locator(".expired-job, [class*='expired' i]").count() > 0
    if banner_exists:
        print("    🔍 Expiry detected via banner/selector.")
    
    return len(found_text) > 0 or banner_exists


def naukri_apply(matched_path=MATCHED_PATH):
    if not os.path.exists(matched_path): return
    with open(matched_path, 'r') as f: jobs = json.load(f).get("approved_jobs", [])
    if not jobs: return

    registry = get_registry()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f: context.add_cookies(json.load(f))
        
        page = context.new_page()
        page.set_default_timeout(60000)

        for job in jobs:
            company_name = job.get('company', 'Unknown')
            print(f"\n🚀 Processing: {company_name}")
            try:
                page.goto(job['url'], wait_until="domcontentloaded")
                time.sleep(4)

                if check_success(page):
                    print("  ✅ Already applied."); job['status'] = 'applied'
                else:
                    apply_btn = page.locator("button:has-text('Apply'), [class*='applyBtn' i]").first
                    if not apply_btn.is_visible(timeout=5000):
                        if is_expired(page):
                            print("  ⚠️ Job has expired. Removing from active list."); job['status'] = 'expired'
                        else:
                            print("  ❌ Apply button missing."); job['status'] = 'skipped_no_apply_btn'
                            take_screenshot(page, company_name, "no_apply_btn")
                    else:
                        # SUPER SELECTOR for Apply button
                        apply_btn = page.locator("button:has-text('Apply'), .applyBtn, .apply-button, #apply-button, [class*='apply' i], button:has-text('Register to apply')").first
                        
                        if not apply_btn.is_visible(timeout=5000):
                             print("  ❌ Apply button STILL missing after retry."); job['status'] = 'skipped_no_apply_btn'
                             take_screenshot(page, company_name, "no_apply_btn_final")
                             continue

                        apply_btn.scroll_into_view_if_needed()
                        # Real click via JS + Mouse events
                        page.evaluate("(el) => { el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true})); el.click(); }", apply_btn.element_handle())
                        print("  🔘 Clicked Apply. Waiting for Form/Bot...")
                        time.sleep(8)
                        
                        # Check for new tab (Company site apply)
                        pages = context.pages
                        if len(pages) > 2:
                             print("  ⚠️ New tab detected. Company site apply. Skipping.")
                             job['status'] = 'skipped_external_site'
                             pages[-1].close()
                             continue

                        # Fallback if drawer didn't open
                        if not detect_form_panel(page):
                            print("  ⚠️ Drawer didn't open. Trying aggressive re-click...")
                            page.evaluate("(el) => { el.click(); }", apply_btn.element_handle())
                            time.sleep(8)

                        for round_num in range(15):
                            if check_success(page):
                                print("  ✅ Application Success!"); job['status'] = 'applied'; break
                            
                            # TAKE SCREENSHOT EVERY ROUND FOR DEBUGGING
                            take_screenshot(page, company_name, f"round_{round_num+1}")

                            if not detect_form_panel(page):
                                time.sleep(4)
                                if not detect_form_panel(page):
                                    if check_success(page):
                                        print("  ✅ Application Success!"); job['status'] = 'applied'
                                    else:
                                        print("  ❓ Form vanished."); job['status'] = 'skipped_unknown_state'
                                        take_screenshot(page, company_name, "form_vanished")
                                    break

                            questions = extract_questions(page)
                            if not questions:
                                print("    ⚠️ No questions found. Waiting..."); time.sleep(4)
                                questions = extract_questions(page); 
                                if not questions: 
                                    take_screenshot(page, company_name, "no_questions_found")
                                    break

                            print(f"    📝 Step {round_num+1}: Found {len(questions)} question(s)")
                            answer_questions(page, questions, registry)
                            submit_form(page)
                        else:
                            print("  ⚠️ Max rounds."); job['status'] = 'skipped_too_many_rounds'
                            take_screenshot(page, company_name, "max_rounds_reached")

            except Exception as e:
                print(f"  ⚠️ Error: {str(e).split('\\n')[0]}")
                job['status'] = 'error'
                take_screenshot(page, company_name, "exception")

            # Update status in the matched file (Saved for EVERY branch now)
            with open(matched_path, 'w') as f: json.dump({"approved_jobs": jobs}, f, indent=4)
            time.sleep(1)

        browser.close()


if __name__ == "__main__":
    naukri_apply()
