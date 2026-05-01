# Troubleshooting Naukri: The "Ghost Apply" Issue

This document serves as a foundational reference for identifying and fixing systemic failures in the Naukri auto-apply pipeline, specifically when the "Apply" button appears to be clicked but fails to trigger the application drawer.

## 🔍 Symptom
- **Behavior:** The script logs "Clicking Apply..." and "Success (One-Click)" or "Form vanished," but the application is not actually submitted.
- **Evidence:** Screenshots show the browser stuck on the Job Description page. HTML snapshots confirm the `chatbot_Drawer` or `chatbot_MessageContainer` are missing from the DOM.
- **Verification:** Re-visiting the URL shows the "Apply" button is still present (not changed to "Applied").

## 🛠️ Root Causes & Investigation Steps

### 1. Bot Detection (Primary)
Naukri uses aggressive fingerprinting. Standard Playwright clicks can be intercepted.
- **Identification:** If a standalone script with the same logic works but the main script fails, fingerprinting is likely the cause.
- **Solution:** 
    - Integrate `playwright-stealth`.
    - Use human-like interactions: `page.mouse.move()` to the button's center before `page.mouse.click()`.
    - Set a realistic `User-Agent`.

### 2. Timing & Event Listeners
Naukri is a heavy Single Page Application (SPA). The "Apply" button often renders before the JavaScript event listeners are attached.
- **Identification:** Button is "visible" in the DOM but unresponsive to clicks.
- **Solution:** 
    - Increase `time.sleep()` after `page.goto()` to **10 seconds**.
    - Use `wait_until="domcontentloaded"` or `networkidle` (carefully).

### 3. Selector Ambiguity
Naukri sometimes renders multiple "Apply" buttons (e.g., one in the header, one in the body). Some may be placeholders or hidden.
- **Identification:** Check the `count()` of the locator. If `> 1`, you might be clicking the wrong one.
- **Solution:** 
    - Prioritize ID-based selectors: `#apply-button`.
    - Use strict locators: `.first` or specific parent containers like `.styles_jhc__apply-button-container__5Bqnb`.

## 🧪 The "Proof Mandate" Debugging Loop
When this issue recurs, follow this exact loop:

1.  **Isolate:** Create a standalone `debug_single_job.py` using a known failing URL.
2.  **Evidence:** Use the improved `take_screenshot` which saves **paired** `.png` and `.html` files.
3.  **Validate DOM:** Search the `.html` for `chatbot_Drawer`. If missing after click, the click failed.
4.  **Stealth Test:** Run with and without `stealth_sync(page)`.
5.  **Refine Click:** Swap between `apply_btn.click()`, `page.mouse.click()`, and `page.evaluate("(el) => el.click()")`.

## 🪲 Checkboxes and Radio Buttons Loop
- **Symptom:** The chatbot repeatedly asks the same question (like city selection or notice period) and fails to advance after clicking "Save".
- **Root Cause:** The UI framework requires native clicks on labels. JavaScript `.click()` or dispatching events on the input itself often unchecks the box or fails to trigger the framework's state manager.
- **Solution:**
    - Use Playwright's native `page.locator(f"label:has-text('{target}')").click()`.
    - Avoid evaluating JS to manually set `input.checked = true` unless as a final fallback.
    - Always ensure the "Save" button `disabled` attribute is explicitly removed using `page.evaluate()` after answering.
    - Implement a "stuck counter" in `naukri_auto_apply.py` that fails the job if the exact same question is extracted 3 rounds in a row.

## 🚀 Proven Configuration (Last Updated: 2026-05-01)
```python
# Context
context = browser.new_context(
    viewport={'width': 1440, 'height': 900},
    user_agent="Mozilla/5.0...",
    java_script_enabled=True
)
# Stealth
stealth_sync(page)
# Navigation
page.goto(url, wait_until="domcontentloaded")
time.sleep(10)
# Click
box = apply_btn.bounding_box()
page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2)
page.mouse.click(...)
```

## 📉 Known Success Indicators
- **Verified Success:** The presence of the green "Applied" button (`button:has-text('Applied')`) or specific success text in `.chatbot_MessageContainer`.
- **External Portal:** A new tab opening or the current URL changing away from `naukri.com`.
