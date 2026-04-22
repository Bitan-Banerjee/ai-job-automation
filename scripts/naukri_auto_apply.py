import os
import json
import time
import random
from playwright.sync_api import sync_playwright

try:
    from auto_apply import get_batch_answers_from_gemini, REGISTRY_PATH
except ImportError:
    REGISTRY_PATH = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATCHED_PATH = os.path.join(BASE_DIR, 'data', 'matched_jobs.json')
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')
if not REGISTRY_PATH:
    REGISTRY_PATH = os.path.join(BASE_DIR, 'data', 'job_qa_registry.json')


def get_registry():
    if not os.path.exists(REGISTRY_PATH): return {}
    with open(REGISTRY_PATH, 'r') as f: return json.load(f)


def save_registry(registry):
    with open(REGISTRY_PATH, 'w') as f: json.dump(registry, f, indent=4)


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

        // 2. INPUTS (Priority: Chatbot text area)
        const chatInput = drawer.querySelector('.textArea, [contenteditable="true"], input:not([type="hidden"]), textarea');
        if (chatbotQuestion && chatInput) {
            questions.push({
                question: chatbotQuestion,
                type: chatInput.tagName === 'INPUT' || chatInput.tagName === 'TEXTAREA' ? 'text' : 'contenteditable',
                options: [],
                index: 0
            });
        }

        // 3. PILLS/OPTIONS (If no text input)
        if (questions.length === 0 && chatbotQuestion) {
            const options = Array.from(drawer.querySelectorAll('.chipMsg, .pill, .option, [class*="chip" i], [class*="pill" i], label'))
                .map(o => o.innerText.trim())
                .filter(t => t.length > 0 && t.length < 50 && t !== chatbotQuestion && !t.includes('Save'));
            if (options.length > 0) {
                questions.push({
                    question: chatbotQuestion,
                    type: 'styled_radio',
                    options: options.map(o => ({ value: o, text: o })),
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
    """Answer questions with dynamic UI support."""
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
            page.evaluate("""([ans]) => {
                const input = document.querySelector('.textArea, [contenteditable="true"], .chatbot_Drawer input, .chatbot_Drawer textarea');
                if (input) {
                    input.focus();
                    if (input.tagName === 'INPUT' || input.tagName === 'TEXTAREA') { input.value = ans; }
                    else { input.innerText = ans; }
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }""", [ans])
        elif q['type'] == 'styled_radio':
            page.evaluate("""([ans]) => {
                const findAndClick = (val) => {
                    const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                    for (const r of radios) {
                        const lbl = document.querySelector(`label[for="${r.id}"]`) || r.parentElement;
                        if (lbl && lbl.innerText.trim().toLowerCase() === val.toLowerCase()) {
                            r.checked = true;
                            r.dispatchEvent(new Event('change', { bubbles: true }));
                            r.dispatchEvent(new Event('click', { bubbles: true }));
                            return true;
                        }
                    }
                    const targets = Array.from(document.querySelectorAll('.chatbot_Drawer .chipMsg, .pill, label, .option, button, span'));
                    const match = targets.find(t => t.innerText.trim().toLowerCase() === val.toLowerCase());
                    if (match) { match.click(); return true; }
                    return false;
                };
                findAndClick(ans);
            }""", [ans])
        time.sleep(1)


def submit_form(page):
    """Submit current step."""
    try:
        btn = page.locator(".sendMsg, .sendMsgbtn_container, .chatBot-ic-send, button:has-text('Save'), button:has-text('Submit'), button:has-text('Next'), button:has-text('Apply')").last
        btn.click(force=True)
        print("    📨 Clicked Save/Submit")
        time.sleep(4)
        return True
    except: return False


def check_success(page):
    """Comprehensive success verification."""
    keys = ["successfully applied", "application submitted", "applied successfully", "already applied", "thank you for showing interest", "application sent", "applied on", "applied today"]
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    if any(k in body for k in keys): return True
    
    applied_btn = page.locator("button:has-text('Applied'), [class*='applied' i]").first
    return applied_btn.is_visible(timeout=3000)


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
            print(f"\n🚀 Processing: {job.get('company', 'Unknown')}")
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
                    else:
                        apply_btn.click()
                        print("  🔘 Clicked Apply. Waiting for Form/Bot...")
                        time.sleep(8)

                        for round_num in range(15):
                            if check_success(page):
                                print("  ✅ Application Success!"); job['status'] = 'applied'; break
                            
                            if not detect_form_panel(page):
                                time.sleep(4)
                                if not detect_form_panel(page):
                                    if check_success(page):
                                        print("  ✅ Application Success!"); job['status'] = 'applied'
                                    else:
                                        print("  ❓ Form vanished."); job['status'] = 'skipped_unknown_state'
                                    break

                            questions = extract_questions(page)
                            if not questions:
                                print("    ⚠️ No questions found. Waiting..."); time.sleep(4)
                                questions = extract_questions(page); 
                                if not questions: break

                            print(f"    📝 Step {round_num+1}: Found {len(questions)} question(s)")
                            answer_questions(page, questions, registry)
                            submit_form(page)
                        else:
                            print("  ⚠️ Max rounds."); job['status'] = 'skipped_too_many_rounds'

            except Exception as e:
                print(f"  ⚠️ Error: {str(e).split('\\n')[0]}")
                job['status'] = 'error'

            # Update status in the matched file (Saved for EVERY branch now)
            with open(matched_path, 'w') as f: json.dump({"approved_jobs": jobs}, f, indent=4)
            time.sleep(1)

        browser.close()


if __name__ == "__main__":
    naukri_apply()
