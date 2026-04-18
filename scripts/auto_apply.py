import os
import json
import time
import random
import re
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from google import genai

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SESSION_FILE = os.path.join(BASE_DIR, 'data', 'linkedin_session.json')
MATCHED_PATH = os.path.join(BASE_DIR, 'data', 'matched_jobs.json')
REGISTRY_PATH = os.path.join(BASE_DIR, 'data', 'job_qa_registry.json')

def get_batch_answers_from_gemini(questions_list, registry):
    if not questions_list: return {}
    
    print(f"    🧠 Batching {len(questions_list)} new questions to Gemini...")
    
    prompt = f"""
    You are filling out a job application.
    User Data: {json.dumps(registry)}
    
    Answer the following list of questions:
    {json.dumps(questions_list)}
    
    RULES:
    1. You MUST return ONLY a valid JSON dictionary. No markdown, no code blocks, no other text.
    2. Keys MUST be the EXACT question strings provided. Values MUST be the exact answers.
    3. STRICT NUMBER RULE: For durations or experience, return ONLY the integer or decimal.
    4. MULTIPLE CHOICE: If a question includes "(Options: ...)", the value MUST be the exact text of one of those options.
    5. FALLBACK TO ZERO: If a specific skill is asked for that is NOT in the User Data, return "0". 
    6. MAPPING: AWS services -> 'years_experience_aws'. RDBMS -> 'years_experience_sql'.
    """
    
    fallback_models = ['gemini-flash-latest', 'gemini-2.5-flash', 'gemini-flash-lite-latest']
    
    for attempt in range(len(fallback_models)):
        model_name = fallback_models[attempt]
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            if not response or not response.text: continue
            
            text = response.text.strip()
            if text.startswith("`" * 3 + "json"): text = text[7:-3].strip()
            elif text.startswith("`" * 3): text = text[3:-3].strip()
            
            new_answers = json.loads(text)
            return new_answers
        except Exception as e: 
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "503" in error_msg:
                print(f"    ⚠️ Rate Limit/Unavailable on {model_name}. Switching...")
                continue
            else:
                print(f"    ⚠️ API Error on {model_name}: {error_msg[:100]}")
                continue
    return {}

def handle_questions(page, registry):
    questions_to_ask = []
    
    # --- PHASE 1: SCRAPE & BATCH ---
    for field in page.query_selector_all(".artdeco-modal input[type='text'], .artdeco-modal input[type='number'], .artdeco-modal textarea"):
        if not field.input_value(): 
            label = page.query_selector(f"label[for='{field.get_attribute('id')}']")
            q_text = label.inner_text().strip() if label else ""
            if q_text and q_text not in registry: questions_to_ask.append(q_text)

    for dropdown in page.query_selector_all(".artdeco-modal select"):
        label = page.query_selector(f"label[for='{dropdown.get_attribute('id')}']")
        q_text = label.inner_text().strip() if label else ""
        options = [opt.inner_text().strip() for opt in dropdown.query_selector_all("option") if "Select" not in opt.inner_text() and opt.inner_text().strip()]
        if options:
            full_q = f"{q_text} (Options: {', '.join(options)})"
            if full_q not in registry: questions_to_ask.append(full_q)

    for fieldset in page.query_selector_all(".artdeco-modal fieldset"):
        if not fieldset.query_selector("input:checked"): 
            legend = fieldset.query_selector("legend")
            q_text = legend.inner_text().strip() if legend else ""
            labels = fieldset.query_selector_all("label")
            options = [l.inner_text().strip() for l in labels if l.inner_text().strip()]
            if options:
                full_q = f"{q_text} (Options: {', '.join(options)})"
                if full_q not in registry: questions_to_ask.append(full_q)

    # --- PHASE 2: ASK AI & SAVE ---
    if questions_to_ask:
        new_answers = get_batch_answers_from_gemini(questions_to_ask, registry)
        if new_answers:
            registry.update(new_answers)
            try:
                with open(REGISTRY_PATH, 'w') as f: json.dump(registry, f, indent=4)
                print(f"    💾 Batch saved {len(new_answers)} new answers to registry.")
            except: pass

    # --- PHASE 3: FILL THE PAGE ---
    for field in page.query_selector_all(".artdeco-modal input[type='text'], .artdeco-modal input[type='number'], .artdeco-modal textarea"):
        label = page.query_selector(f"label[for='{field.get_attribute('id')}']")
        q_text = label.inner_text().strip() if label else ""
        if q_text in registry: field.fill(str(registry[q_text]))

    for dropdown in page.query_selector_all(".artdeco-modal select"):
        label = page.query_selector(f"label[for='{dropdown.get_attribute('id')}']")
        q_text = label.inner_text().strip() if label else ""
        options = [opt.inner_text().strip() for opt in dropdown.query_selector_all("option") if "Select" not in opt.inner_text() and opt.inner_text().strip()]
        if options:
            full_q = f"{q_text} (Options: {', '.join(options)})"
            if full_q in registry:
                try: dropdown.select_option(label=str(registry[full_q]))
                except: dropdown.select_option(index=1) 

    for fieldset in page.query_selector_all(".artdeco-modal fieldset"):
        if not fieldset.query_selector("input:checked"):
            legend = fieldset.query_selector("legend")
            q_text = legend.inner_text().strip() if legend else ""
            labels = fieldset.query_selector_all("label")
            options = [l.inner_text().strip() for l in labels if l.inner_text().strip()]
            if options:
                full_q = f"{q_text} (Options: {', '.join(options)})"
                if full_q in registry:
                    ans = str(registry[full_q]).lower()
                    for lbl in labels:
                        if ans == lbl.inner_text().strip().lower():
                            lbl.click()
                            break

def auto_apply():
    if not os.path.exists(REGISTRY_PATH): return
    with open(REGISTRY_PATH, 'r') as f: registry = json.load(f)
    with open(MATCHED_PATH, 'r') as f: jobs = json.load(f).get("approved_jobs", [])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f: context.add_cookies(json.load(f))
        
        page = context.new_page()
        page.set_default_timeout(60000)

        for job in jobs:
            score = job.get('ai_score', 0)
            if score < 80:
                print(f"\n⏭️  Skipping {job.get('company', 'Unknown')}: AI Score ({score}) is below the 80 threshold.")
                continue
                
            print(f"\n🚀 Processing: {job.get('company', 'Unknown')} (Score: {score})")
            try:
                page.goto(job['url'], wait_until="domcontentloaded")
            except Exception as e:
                print(f"  ⚠️ Navigation failed: {e}")
                continue
            
            time.sleep(random.uniform(2, 4))
            page.mouse.wheel(0, 500)
            time.sleep(2)

            try:
                if page.locator("button:has-text('Applied')").is_visible(timeout=2000):
                    print(f"  ✅ Already applied to {job['company']}. Skipping.")
                    continue
            except: pass

            button_clicked = False
            print("  🕵️ Hunting for the Easy Apply button...")

            if not button_clicked:
                try:
                    btn = page.get_by_role("button", name=re.compile("Easy Apply", re.IGNORECASE)).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        print("    🔘 Clicked Easy Apply via ARIA Role")
                        button_clicked = True
                except: pass

            if not button_clicked:
                try:
                    btn = page.locator("button:has-text('Easy Apply')").first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        print("    🔘 Clicked Easy Apply via Text Locator")
                        button_clicked = True
                except: pass

            if not button_clicked:
                try:
                    clicked = page.evaluate("""() => {
                        const elements = Array.from(document.querySelectorAll('button, a, div[role="button"]')).filter(el => el.offsetWidth > 0 && el.offsetHeight > 0);
                        const target = elements.find(el => el.innerText && el.innerText.trim().includes('Easy Apply'));
                        if (target) { target.click(); return true; }
                        return false;
                    }""")
                    if clicked: 
                        print("    🔘 Clicked Easy Apply via JavaScript Injection")
                        button_clicked = True
                except: pass

            if not button_clicked:
                print(f"  ❌ Easy Apply button genuinely not found. Moving on.")
                continue

            # We removed the strict modal wait block that was crashing things.
            # We let the main loop handle the modal safely.

            for loop_count in range(10):
                time.sleep(2)
                
                modal = page.locator(".artdeco-modal")
                if not modal.is_visible():
                    break
                    
                handle_questions(page, registry)
                
                file_input = modal.locator("input[type='file']")
                if file_input.count() > 0:
                    target_resume = job.get('tailored_resume_path', '')
                    if os.path.exists(target_resume):
                        try:
                            file_input.first.set_input_files(target_resume)
                            print(f"    📄 Attached {os.path.basename(target_resume)}.")
                        except Exception as e: 
                            pass
                
                if modal.locator(".artdeco-inline-feedback--error").count() > 0:
                    print("  ⚠️ Form validation failing. Skipping job to avoid infinite loop.")
                    break

                # Back to the explicit text-based button matching that worked!
                next_btn = modal.locator("button:has-text('Next')").first
                review_btn = modal.locator("button:has-text('Review')").first
                submit_btn = modal.locator("button:has-text('Submit application')").first

                if submit_btn.is_visible():
                    print(f"  🏁 Finalizing application for {job['company']}...")
                    submit_btn.click()
                    time.sleep(3)
                    print(f"  ✅ SUCCESS! Application fully submitted.")
                    job['status'] = 'applied'
                    with open(MATCHED_PATH, 'w') as f:
                        json.dump({"approved_jobs": jobs}, f, indent=4)
                    break
                elif review_btn.is_visible():
                    review_btn.click()
                    print("    ➡️ Clicked 'Review'")
                elif next_btn.is_visible():
                    next_btn.click()
                    print("    ➡️ Clicked 'Next'")
                else:
                    print("  ⚠️ Could not find Next/Review/Submit buttons. Exiting modal.")
                    break

        browser.close()

if __name__ == "__main__":
    auto_apply()
